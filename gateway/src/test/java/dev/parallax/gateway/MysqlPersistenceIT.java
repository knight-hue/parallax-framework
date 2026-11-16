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
    @Autowired dev.parallax.gateway.platform.PlatformWorkerCoordinator coordinator;
    @Autowired dev.parallax.gateway.platform.PlatformOutboxStore outbox;
    @Autowired dev.parallax.gateway.platform.PlatformArtifactService artifacts;

    @Test
    void concurrentOutboxClaimsAndExpiredOwnershipHoldOnMysql() throws Exception {
        // This verifier owns an isolated database; keep unrelated fixtures out of the claim set.
        jdbc.update("UPDATE platform_outbox SET status='SUPERSEDED',claim_token=NULL,claim_until=NULL");
        var user=identity.provision("test","mysql-outbox-"+UUID.randomUUID(),"test-password-123");
        var org=identity.createOrganization(user.id(),"outbox");
        var project=identity.createProject(user.id(),org.id(),"project");
        var repo=catalog.register(user.id(),project.id(),"api","https://github.com/team/api");
        var policy=catalog.publish(user.id(),project.id(),new dev.parallax.gateway.platform.PlatformCatalogService.PolicyConfig(4,2,3,2,true,1000,3600));
        tasks.configureBudget("test-admin",org.id(),400);
        for(int i=0;i<4;i++) tasks.submit(user.id(),project.id(),"request-"+i,new dev.parallax.gateway.platform.PlatformTaskService.Submission(repo.id(),policy.id(),"a".repeat(40),100));
        var claims=new java.util.ArrayList<dev.parallax.gateway.platform.PlatformOutboxStore.Claim>();
        try(var pool=java.util.concurrent.Executors.newFixedThreadPool(4)) {
            var jobs=java.util.stream.IntStream.range(0,12).mapToObj(i -> (java.util.concurrent.Callable<java.util.Optional<dev.parallax.gateway.platform.PlatformOutboxStore.Claim>>) outbox::claim).toList();
            for(var future:pool.invokeAll(jobs)) future.get().ifPresent(claims::add);
        }
        assertThat(claims).hasSize(4);
        assertThat(claims.stream().map(dev.parallax.gateway.platform.PlatformOutboxStore.Claim::id).distinct()).hasSize(4);
        var expired=claims.getFirst();
        jdbc.update("UPDATE platform_outbox SET claim_until=? WHERE id=?",Timestamp.from(Instant.now().minusSeconds(1)),expired.id());
        var reclaimed=outbox.claim().orElseThrow();
        assertThat(reclaimed.id()).isEqualTo(expired.id());
        assertThat(reclaimed.claimToken()).isNotEqualTo(expired.claimToken());
        assertThat(outbox.complete(expired,true)).isFalse();
        assertThat(outbox.retry(expired)).isFalse();
        assertThat(outbox.complete(reclaimed,true)).isTrue();
        for(var claim:claims) if(!claim.id().equals(expired.id())) assertThat(outbox.complete(claim,true)).isTrue();
        assertThat(tasks.budget(user.id(),org.id()).reservedTokens()).isEqualTo(400);
        assertThat(tasks.reconcile(org.id()).consistent()).isTrue();
    }

    @Test
    void workerInboxHandlesConcurrentOrganizationsAndDuplicateSettlementOnMysql() throws Exception {
        var contracts=new java.util.ArrayList<dev.parallax.gateway.task.WorkerTask>();
        var users=new java.util.ArrayList<String>();
        for(int i=0;i<2;i++) {
            var user=identity.provision("test","mysql-worker-"+UUID.randomUUID(),"test-password-123");
            users.add(user.id());
            var org=identity.createOrganization(user.id(),"worker");
            var project=identity.createProject(user.id(),org.id(),"project");
            var repo=catalog.register(user.id(),project.id(),"api","https://github.com/team/api");
            var config=new dev.parallax.gateway.platform.PlatformCatalogService.PolicyConfig(4,2,3,2,true,1000,3600);
            var policy=catalog.publish(user.id(),project.id(),config);
            tasks.configureBudget("test-admin",org.id(),100);
            var input=new dev.parallax.gateway.platform.PlatformTaskService.Submission(repo.id(),policy.id(),"a".repeat(40),100);
            var task=tasks.submit(user.id(),project.id(),"request",input);
            contracts.add(task.dispatch());
            assertThat(coordinator.prepareDispatch(task.id(),1,1)).isTrue();
        }
        try(var pool=java.util.concurrent.Executors.newFixedThreadPool(4)) {
            var starts=contracts.stream().map(t -> (java.util.concurrent.Callable<Boolean>) () -> coordinator.receive(new dev.parallax.gateway.task.WorkerEvent(1,UUID.randomUUID().toString(),t.taskId(),1,1,1,dev.parallax.gateway.task.WorkerEvent.Kind.STARTED,Instant.now(),null,0,0)).accepted()).toList();
            for(var future:pool.invokeAll(starts)) assertThat(future.get()).isTrue();
            String content="{\"report\":\"中文 😀\"}";
            String digest=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(content.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
            for(var t:contracts) {
                var upload=new dev.parallax.gateway.platform.PlatformArtifactService.Upload(t.taskId(),1,1,UUID.randomUUID().toString(),digest,content);
                var saved=artifacts.put(upload);
                assertThat(artifacts.put(upload)).isEqualTo(saved);
            }
            var done=contracts.stream().map(t -> new dev.parallax.gateway.task.WorkerEvent(1,UUID.randomUUID().toString(),t.taskId(),1,1,2,dev.parallax.gateway.task.WorkerEvent.Kind.SUCCEEDED,Instant.now(),digest,30,10)).toList();
            var jobs=java.util.stream.IntStream.range(0,8).mapToObj(i -> (java.util.concurrent.Callable<Boolean>) () -> coordinator.receive(done.get(i%2)).accepted()).toList();
            int accepted=0;for(var future:pool.invokeAll(jobs)) if(future.get()) accepted++;
            assertThat(accepted).isEqualTo(2);
        }
        for(int i=0;i<contracts.size();i++) {
            var t=contracts.get(i);
            assertThat(tasks.budget(users.get(i),t.organizationId()).usedTokens()).isEqualTo(40);
            assertThat(tasks.reconcile(t.organizationId()).consistent()).isTrue();
            assertThat(coordinator.events(users.get(i),t.projectId(),t.taskId(),0,100).items()).hasSize(4);
        }
    }

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
    void usesRealMysqlInnoDBAndValidatesFlyway() throws Exception {
        assertThat(jdbc.queryForObject("SELECT VERSION()", String.class)).startsWith("8.");
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'platform_project' AND engine = 'InnoDB'", Integer.class)).isEqualTo(1);
        // 迁移脚本增加时这条断言自动跟随，避免每次加 V*.sql 都要改测试。
        int migrations = new org.springframework.core.io.support.PathMatchingResourcePatternResolver()
                .getResources("classpath:db/mysql/V*.sql").length;
        assertThat(migrations).isPositive();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM flyway_schema_history WHERE success = TRUE", Integer.class)).isEqualTo(migrations);
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

}
