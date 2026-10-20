package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.DriverManager;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;

import dev.parallax.gateway.identity.ApiKeyService;
import dev.parallax.gateway.identity.QuotaService;
import dev.parallax.gateway.platform.PlatformIdentityService;
import dev.parallax.gateway.platform.ProjectRole;
import dev.parallax.gateway.runs.AuditRunRepository;
import dev.parallax.gateway.runs.RunService;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DataAccessException;
import org.flywaydb.core.Flyway;
import dev.parallax.gateway.platform.LegacyDatabaseTransfer;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
@ActiveProfiles("mysql")
@EnabledIfSystemProperty(named = "parallax.test.mysql", matches = "true")
class MysqlPersistenceIT {
    @Autowired JdbcTemplate jdbc;
    @Autowired PlatformIdentityService identity;
    @Autowired ApiKeyService apiKeys;
    @Autowired QuotaService quota;
    @Autowired RunService runs;
    @Autowired AuditRunRepository runRepository;
    @Autowired dev.parallax.gateway.platform.PlatformCatalogService catalog;
    @Autowired dev.parallax.gateway.platform.PlatformTaskService tasks;

    @Test
    void atomicBudgetReservationAndIdempotencyHoldUnderRealMysqlContention() throws Exception {
        var user=identity.provision("test","mysql-budget-"+UUID.randomUUID(),"test-password-123");
        var org=identity.createOrganization(user.id(),"budget");
        var project=identity.createProject(user.id(),org.id(),"project");
        var repo=catalog.register(user.id(),project.id(),"api","https://github.com/team/api");
        var config=new dev.parallax.gateway.platform.PlatformCatalogService.PolicyConfig(4,2,3,2,true,1000,3600);
        var policy=catalog.publish(user.id(),project.id(),config);
        tasks.configureBudget("test-admin",org.id(),300);
        var input=new dev.parallax.gateway.platform.PlatformTaskService.Submission(repo.id(),policy.id(),"a".repeat(40),100);
        try(var pool=java.util.concurrent.Executors.newFixedThreadPool(6)) {
            var retries=java.util.stream.IntStream.range(0,8).mapToObj(i -> (java.util.concurrent.Callable<String>)
                    () -> tasks.submit(user.id(),project.id(),"same",input).id()).toList();
            var ids=new java.util.HashSet<String>();
            for(var future:pool.invokeAll(retries)) ids.add(future.get());
            assertThat(ids).hasSize(1);
            var jobs=java.util.stream.IntStream.range(0,20).mapToObj(i -> (java.util.concurrent.Callable<Boolean>) () -> {
                try { tasks.submit(user.id(),project.id(),"new-"+i,input);return true; }
                catch(dev.parallax.gateway.common.ApiException ex) { assertThat(ex.getStatus().value()).isEqualTo(429);return false; }
            }).toList();
            int accepted=0;
            for(var future:pool.invokeAll(jobs)) if(future.get()) accepted++;
            assertThat(accepted).isEqualTo(2);
            assertThat(tasks.budget(user.id(),org.id()).reservedTokens()).isEqualTo(300);
            String taskId=ids.iterator().next();
            tasks.cancel(user.id(),project.id(),taskId);tasks.cancel(user.id(),project.id(),taskId);
            assertThat(tasks.budget(user.id(),org.id()).reservedTokens()).isEqualTo(200);
            assertThat(tasks.reconcile(org.id()).consistent()).isTrue();
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_budget_ledger WHERE task_id=? AND kind='SETTLE'",Integer.class,taskId)).isEqualTo(1);
            var other=identity.createProject(user.id(),org.id(),"other");
            var foreign=catalog.register(user.id(),other.id(),"api","https://github.com/team/other");
            assertThatThrownBy(()->jdbc.update("UPDATE platform_task SET repository_id=? WHERE id=?",foreign.id(),taskId)).isInstanceOf(DataIntegrityViolationException.class);
        }
    }

    @Test
    void concurrentPolicyPublishersUseCurrentReadsUnderMysqlRepeatableRead() throws Exception {
        var user = identity.provision("test", "mysql-catalog-" + UUID.randomUUID(), "test-password-123");
        var org = identity.createOrganization(user.id(), "catalog");
        var project = identity.createProject(user.id(), org.id(), "project");
        var repository = catalog.register(user.id(), project.id(), "api", "https://github.com/team/api");
        assertThat(catalog.repository(user.id(), project.id(), repository.id())).isEqualTo(repository);
        var config = new dev.parallax.gateway.platform.PlatformCatalogService.PolicyConfig(4,2,3,2,true,1000,3600);
        try (var pool = java.util.concurrent.Executors.newFixedThreadPool(4)) {
            var jobs = java.util.stream.IntStream.range(0,8).mapToObj(i -> (java.util.concurrent.Callable<Integer>)
                    () -> catalog.publish(user.id(), project.id(), config).versionNumber()).toList();
            var versions = new java.util.ArrayList<Integer>();
            for (var future : pool.invokeAll(jobs)) versions.add(future.get());
            assertThat(versions).containsExactlyInAnyOrder(1,2,3,4,5,6,7,8);
        }
    }

    @DynamicPropertySource
    static void mysql(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> System.getenv("PARALLAX_TEST_DB_URL"));
        registry.add("spring.datasource.username", () -> "parallax_test");
        registry.add("spring.datasource.password", () -> System.getenv("PARALLAX_TEST_DB_PASSWORD"));
        registry.add("parallax.identity.enabled", () -> "true");
    }

    @Test
    void usesRealMysqlInnoDBAndValidatesFlyway() {
        assertThat(jdbc.queryForObject("SELECT VERSION()", String.class)).startsWith("8.");
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'platform_project' AND engine = 'InnoDB'", Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM flyway_schema_history WHERE success = TRUE", Integer.class)).isEqualTo(6);
    }

    @Test
    void platformMembershipAndRealForeignKeysAreEnforced() {
        var user = identity.provision("test", "mysql-" + UUID.randomUUID(), "test-password-123");
        var org = identity.createOrganization(user.id(), "MySQL organization");
        var project = identity.createProject(user.id(), org.id(), "payments");
        assertThat(identity.project(user.id(), project.id(), ProjectRole.VIEWER)).isEqualTo(project);
        assertThatThrownBy(() -> jdbc.update("INSERT INTO platform_membership (organization_id, user_id, role) VALUES (?, ?, 'VIEWER')", org.id(), UUID.randomUUID().toString()))
                .isInstanceOf(DataIntegrityViolationException.class);
        assertThatThrownBy(() -> jdbc.update("INSERT INTO platform_membership (organization_id, user_id, role) VALUES (?, ?, 'SUPERUSER')", org.id(), user.id()))
                .isInstanceOf(DataAccessException.class).hasMessageContaining("3819");
    }

    @Test
    void hibernateAndIndependentJdbcRoundTripUtcAndUsage() throws Exception {
        var key = apiKeys.issue("mysql-" + UUID.randomUUID(), "VIEWER", "default");
        String id = key.credential().getId();
        String submissionId = runs.registerSubmission(id, "repo-" + UUID.randomUUID(), "question");
        String runId = "run-" + UUID.randomUUID();
        runs.attachUpstreamRunId(submissionId, runId);
        runs.complete(runId, id, "done", 100, 25, 1.0, "{}", "finished");
        assertThat(quota.record(id, runId, 100, 25, "trace")).isTrue();
        assertThat(quota.record(id, runId, 100, 25, "trace")).isFalse();
        assertThat(quota.usageOf(id, Instant.EPOCH).tokens()).isEqualTo(125);
        Instant precise = Instant.parse("2026-10-20T12:34:56.123456Z");
        jdbc.update("UPDATE audit_run SET submitted_at = ? WHERE id = ?", Timestamp.from(precise), submissionId);
        assertThat(runRepository.findById(submissionId).orElseThrow().getSubmittedAt()).isEqualTo(precise);
        try (var connection = DriverManager.getConnection(System.getenv("PARALLAX_TEST_DB_URL"), "parallax_test", System.getenv("PARALLAX_TEST_DB_PASSWORD"));
             var statement = connection.prepareStatement("SELECT total_tokens FROM usage_ledger WHERE run_id = ?")) {
            statement.setString(1, runId);
            try (var rows = statement.executeQuery()) {
                assertThat(rows.next()).isTrue();
                assertThat(rows.getLong(1)).isEqualTo(125);
            }
        }
    }

    @Test
    void offlineTransferChecksEveryColumnAndRefusesNonemptyDestination() throws Exception {
        String sourceUrl = "jdbc:h2:mem:transfer-" + UUID.randomUUID() + ";MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1";
        boolean postgres = System.getenv("PARALLAX_TRANSFER_TEST_SOURCE_URL") != null;
        if (postgres) sourceUrl = System.getenv("PARALLAX_TRANSFER_TEST_SOURCE_URL");
        String sourceUser = postgres ? "parallax_test" : "sa";
        String sourcePassword = postgres ? System.getenv("PARALLAX_TEST_DB_PASSWORD") : "";
        String targetUrl = System.getenv("PARALLAX_TEST_DB_URL").replace("/parallax_test?", "/parallax_transfer?");
        String password = System.getenv("PARALLAX_TEST_DB_PASSWORD");
        Flyway.configure().dataSource(sourceUrl, sourceUser, sourcePassword).locations("classpath:db/migration").load().migrate();
        Flyway.configure().dataSource(targetUrl, "parallax_test", password).locations("classpath:db/mysql").load().migrate();
        try (var source = DriverManager.getConnection(sourceUrl, sourceUser, sourcePassword);
             var target = DriverManager.getConnection(targetUrl, "parallax_test", password)) {
            try (var insert = source.prepareStatement("INSERT INTO platform_user (id, username, password_hash, disabled, created_at) VALUES ('user-source', 'source-user', 'not-a-real-hash', FALSE, ?)")) {
                insert.setTimestamp(1, Timestamp.from(Instant.parse("2026-10-20T10:00:00.123456Z")));
                insert.executeUpdate();
            }
            // Exercise every transferred table and nullable/non-null fields, not only an empty schema.
            try (var seed = source.createStatement()) {
                seed.executeUpdate("INSERT INTO api_credential (id,name,key_hash,key_prefix,role,quota_policy_id,created_at,last_used_at) VALUES ('key-source','来源凭据','test-hash','plx_test','VIEWER',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO usage_ledger (id,credential_id,run_id,occurred_at,prompt_tokens,completion_tokens,total_tokens,trace_id) VALUES (42,'key-source','run-source',CURRENT_TIMESTAMP,100,25,125,'trace-source')");
                seed.executeUpdate("INSERT INTO audit_run (id,run_id,credential_id,repo_path,question,status,submitted_at,finished_at,elapsed_s,trace_id,prompt_tokens,completion_tokens,total_tokens,counts_json,stop_reason,error) VALUES ('submission-source','run-source','key-source','repo/代码','审查问题','done',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,1.25,'trace-source',100,25,125,'{}','finished',NULL)");
                seed.executeUpdate("INSERT INTO audit_event (id,run_id,event_type,at,detail,trace_id) VALUES (42,'run-source','completed',CURRENT_TIMESTAMP,'包含中文与 emoji 😀','trace-source')");
                seed.executeUpdate("INSERT INTO platform_organization (id,name,created_at) VALUES ('org-source','测试组织',CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_membership (organization_id,user_id,role) VALUES ('org-source','user-source','OWNER')");
                seed.executeUpdate("INSERT INTO platform_project (id,organization_id,name,created_at) VALUES ('project-source','org-source','测试项目',CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_access_audit (id,actor,action,resource_id,at) VALUES ('access-source','user-source','CREATE_PROJECT','project-source',CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_repository (id,project_id,name,clone_url,created_by,created_at) VALUES ('repository-source','project-source','example','https://github.com/example/repo','user-source',CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_policy_version (id,project_id,version_number,config_json,config_sha256,created_by,created_at) VALUES ('policy-source','project-source',1,'{}','not-a-real-policy-digest','user-source',CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_budget_account (organization_id,token_limit,reserved_tokens,used_tokens,updated_at) VALUES ('org-source',200,0,25,CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_task (id,organization_id,project_id,repository_id,policy_version,created_by,request_key,request_sha256,commit_sha,token_budget,deadline,state,attempt,fencing_token,last_sequence,prompt_tokens,completion_tokens,settled,created_at,updated_at) VALUES ('task-source','org-source','project-source','repository-source','policy-source','user-source','request-source','test-request-hash','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',100,CURRENT_TIMESTAMP,'FAILED',1,1,2,20,5,TRUE,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_budget_ledger (id,organization_id,task_id,kind,tokens,at) VALUES ('reserve-source','org-source','task-source','RESERVE',100,CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_budget_ledger (id,organization_id,task_id,kind,tokens,at) VALUES ('settle-source','org-source','task-source','SETTLE',25,CURRENT_TIMESTAMP)");
                seed.executeUpdate("INSERT INTO platform_outbox (id,task_id,attempt,kind,payload,status,available_at,created_at,published_at) VALUES ('outbox-source','task-source',1,'DISPATCH','{}','PUBLISHED',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)");
            }
            assertThatThrownBy(() -> LegacyDatabaseTransfer.copy(source, target, false)).isInstanceOf(IllegalArgumentException.class);
            assertThat(LegacyDatabaseTransfer.copy(source, target, true)).hasSize(16).allSatisfy(row -> assertThat(row.rows()).isPositive());
            assertThat(LegacyDatabaseTransfer.verify(source, target)).hasSize(16);
            assertThatThrownBy(() -> LegacyDatabaseTransfer.copy(source, target, true)).hasMessageContaining("Destination must be empty");
            try (var change = target.createStatement()) { change.executeUpdate("UPDATE platform_user SET username = 'tampered'"); }
            assertThatThrownBy(() -> LegacyDatabaseTransfer.verify(source, target)).hasMessageContaining("verification mismatch");
        }
    }
}
