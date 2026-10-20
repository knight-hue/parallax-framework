package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.platform.*;
import dev.parallax.gateway.task.TaskState;
import dev.parallax.gateway.task.WorkerProtocol;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT, properties={
        "parallax.gateway.require-auth=true", "parallax.ratelimit.enabled=false",
        "parallax.jwt.secret=0123456789abcdef0123456789abcdef", "parallax.gateway.admin-secret=platform-test-admin"
})
@ActiveProfiles("test")
class PlatformTaskIntegrationTest {
    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired JdbcTemplate jdbc;
    @Autowired TestRestTemplate rest;
    @Autowired JwtService jwt;
    @Autowired PlatformTransactionManager transactionManager;
    private record Fixture(String user,String org,String project,PlatformTaskService.Submission input) { }
    private Fixture fixture(long limit) {
        var user=identity.provision("test","tasks-"+UUID.randomUUID(),"test-password-123");
        var org=identity.createOrganization(user.id(),"team");
        var project=identity.createProject(user.id(),org.id(),"project");
        var repo=catalog.register(user.id(),project.id(),"api","https://github.com/team/api");
        var policy=catalog.publish(user.id(),project.id(),new PlatformCatalogService.PolicyConfig(4,2,3,2,true,1000,3600));
        tasks.configureBudget("test-admin",org.id(),limit);
        return new Fixture(user.id(),org.id(),project.id(),new PlatformTaskService.Submission(repo.id(),policy.id(),"a".repeat(40),100));
    }
    private ResponseEntity<Map> call(HttpMethod method,String path,String token,Object body,String key) {
        var headers=new HttpHeaders(); headers.setBearerAuth(token);
        headers.set("X-Trace-Id","untrusted.trace/value");
        if(key!=null) headers.set("Idempotency-Key",key);
        return rest.exchange(path,method,new HttpEntity<>(body,headers),Map.class);
    }
    private String token(String user) { return jwt.issueUserToken(user,"test"); }
    private String base(Fixture f) { return "/api/v1/platform/projects/"+f.project+"/tasks"; }

    @Test
    void reservationTaskAndOutboxAreDurableAndIdempotent() throws Exception {
        var f=fixture(100);
        var first=tasks.submit(f.user,f.project,"request-1",f.input);
        var replay=tasks.submit(f.user,f.project,"request-1",f.input);
        assertThat(replay).isEqualTo(first);
        assertThat(first.state()).isEqualTo(TaskState.QUEUED);
        assertThat(tasks.budget(f.user,f.org).reservedTokens()).isEqualTo(100);
        String payload=jdbc.queryForObject("SELECT payload FROM platform_outbox WHERE task_id=?",String.class,first.id());
        var contract=WorkerProtocol.readTask(payload);
        assertThat(contract.taskId()).isEqualTo(first.id());
        assertThat(contract.commitSha()).isEqualTo(f.input.commitSha());
        assertThat(contract.policyVersion()).isEqualTo(f.input.policyVersion());
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_budget_ledger WHERE task_id=?",Integer.class,first.id())).isEqualTo(1);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_outbox WHERE task_id=?",Integer.class,first.id())).isEqualTo(1);
        assertThat(tasks.reconcile(f.org).consistent()).isTrue();
        jdbc.update("UPDATE platform_budget_account SET reserved_tokens=0 WHERE organization_id=?",f.org);
        var mismatch=tasks.reconcile(f.org);
        assertThat(mismatch.consistent()).isFalse();
        assertThat(mismatch.expectedReserved()).isEqualTo(100);
        jdbc.update("UPDATE platform_budget_account SET reserved_tokens=100 WHERE organization_id=?",f.org);
        var changed=new PlatformTaskService.Submission(f.input.repositoryId(),f.input.policyVersion(),"b".repeat(40),100);
        assertThatThrownBy(()->tasks.submit(f.user,f.project,"request-1",changed)).isInstanceOf(ApiException.class).hasMessageContaining("different input");
    }

    @Test
    void concurrentDifferentRequestsCannotOverspendAndCancelRefundsOnce() throws Exception {
        var f=fixture(300);
        try(var pool=Executors.newFixedThreadPool(6)) {
            var jobs=IntStream.range(0,20).mapToObj(i -> (Callable<PlatformTaskService.Task>) () -> {
                try{return tasks.submit(f.user,f.project,"request-"+i,f.input);}
                catch(ApiException ex){assertThat(ex.getStatus()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);return null;}
            }).toList();
            var accepted=new java.util.ArrayList<PlatformTaskService.Task>();
            for(var future:pool.invokeAll(jobs)) { var task=future.get(); if(task!=null) accepted.add(task); }
            assertThat(accepted).hasSize(3);
            assertThat(tasks.budget(f.user,f.org)).isEqualTo(new PlatformTaskService.Budget(f.org,300,300,0));
            var task=accepted.getFirst();
            tasks.cancel(f.user,f.project,task.id()); tasks.cancel(f.user,f.project,task.id());
            assertThat(tasks.budget(f.user,f.org).reservedTokens()).isEqualTo(200);
            assertThat(tasks.get(f.user,f.project,task.id()).settled()).isTrue();
            assertThat(jdbc.queryForObject("SELECT status FROM platform_outbox WHERE task_id=?",String.class,task.id())).isEqualTo("SUPERSEDED");
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_budget_ledger WHERE task_id=? AND kind='SETTLE'",Integer.class,task.id())).isEqualTo(1);
        }
    }

    @Test
    void simultaneousRetriesCreateExactlyOneReservation() throws Exception {
        var f=fixture(100);
        try(var pool=Executors.newFixedThreadPool(4)) {
            var jobs=IntStream.range(0,8).mapToObj(i -> (Callable<String>) () -> tasks.submit(f.user,f.project,"same-key",f.input).id()).toList();
            var ids=new java.util.ArrayList<String>();
            for(var future:pool.invokeAll(jobs)) ids.add(future.get());
            assertThat(ids.stream().distinct()).hasSize(1);
            assertThat(tasks.tasks(f.user,f.project,"",100).items()).hasSize(1);
            assertThat(tasks.budget(f.user,f.org).reservedTokens()).isEqualTo(100);
        }
    }

    @Test
    void surroundingTransactionRollbackRestoresBudgetAndRemovesAllSideEffects() {
        var f=fixture(100);
        assertThatThrownBy(()->new TransactionTemplate(transactionManager).execute(status->{
            var task=tasks.submit(f.user,f.project,"rollback",f.input);
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_outbox WHERE task_id=?",Integer.class,task.id())).isEqualTo(1);
            throw new IllegalStateException("injected failure before commit");
        })).hasMessageContaining("injected failure");
        assertThat(tasks.budget(f.user,f.org).reservedTokens()).isZero();
        assertThat(tasks.tasks(f.user,f.project,"",100).items()).isEmpty();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_access_audit WHERE actor=? AND action='TASK_SUBMITTED'",Integer.class,f.user)).isZero();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_budget_ledger WHERE organization_id=?",Integer.class,f.org)).isZero();
    }

    @Test
    void httpRolesPreventQuotaSelfGrantAndCrossTenantReads() {
        var f=fixture(100); var other=fixture(100);
        var response=call(HttpMethod.POST,base(f),token(f.user),f.input,"http-key");
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getHeaders().getFirst("X-Trace-Id")).matches("[A-Za-z0-9_-]{1,64}");
        String id=(String)response.getBody().get("id");
        assertThat(call(HttpMethod.GET,base(f)+"/"+id,token(other.user),null,null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(call(HttpMethod.PUT,"/api/v1/platform/budgets/"+f.org,token(f.user),Map.of("tokenLimit",999999),null).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(call(HttpMethod.PUT,"/api/v1/platform/budgets/"+f.org,jwt.issueAccessToken("operator","ADMIN"),Map.of("tokenLimit",200),null).getStatusCode()).isEqualTo(HttpStatus.OK);
        identity.addMember(f.user,f.org,other.user,ProjectRole.VIEWER);
        assertThat(call(HttpMethod.GET,base(f)+"/"+id,token(other.user),null,null).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(call(HttpMethod.POST,base(f),token(other.user),f.input,"forbidden").getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(call(HttpMethod.POST,base(f)+"/"+id+"/cancel",token(other.user),null,null).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        identity.removeMember(f.user,f.org,other.user);
        assertThat(call(HttpMethod.GET,base(f)+"/"+id,token(other.user),null,null).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void invalidInputsAndQuotaReductionLeaveExistingReservationsIntact() {
        var f=fixture(100); var other=fixture(100);
        var cross=new PlatformTaskService.Submission(other.input.repositoryId(),f.input.policyVersion(),"a".repeat(40),100);
        assertThatThrownBy(()->tasks.submit(f.user,f.project,"cross",cross)).isInstanceOf(ApiException.class);
        assertThat(call(HttpMethod.POST,base(f),token(f.user),f.input,null).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThatThrownBy(()->tasks.submit(f.user,f.project,"invalid",new PlatformTaskService.Submission(f.input.repositoryId(),f.input.policyVersion(),"HEAD",100))).isInstanceOf(ApiException.class);
        var created=tasks.submit(f.user,f.project,"valid",f.input);
        assertThatThrownBy(()->tasks.configureBudget("operator",f.org,99)).hasMessageContaining("below used and reserved");
        assertThat(tasks.budget(f.user,f.org)).isEqualTo(new PlatformTaskService.Budget(f.org,100,100,0));
        tasks.cancel(f.user,f.project,created.id());
        assertThat(tasks.submit(f.user,f.project,"valid",f.input).state()).isEqualTo(TaskState.CANCELED);
        assertThat(tasks.budget(f.user,f.org).reservedTokens()).isZero();
    }
}
