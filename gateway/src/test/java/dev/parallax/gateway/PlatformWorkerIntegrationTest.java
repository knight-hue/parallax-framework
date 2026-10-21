package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.common.ApiException;
import dev.parallax.gateway.platform.*;
import dev.parallax.gateway.task.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT, properties={
        "parallax.gateway.require-auth=true", "parallax.ratelimit.enabled=false",
        "parallax.jwt.secret=0123456789abcdef0123456789abcdef", "parallax.gateway.admin-secret=platform-test-admin"
})
@ActiveProfiles("test")
class PlatformWorkerIntegrationTest {
    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired PlatformWorkerCoordinator coordinator;
    @Autowired JdbcTemplate jdbc;
    @Autowired TestRestTemplate rest;
    @Autowired JwtService jwt;
    @Autowired PlatformExecutionSnapshot snapshots;
    @Autowired PlatformArtifactService artifacts;
    @Autowired PlatformRepairReviewService reviews;

    @Test
    void executionSnapshotRequiresPrivateCredentialAndAnExactLeasedContract() {
        var f=fixture();
        assertThatThrownBy(()->snapshots.resolve(f.task.dispatch())).hasMessageContaining("active dispatch lease");
        dispatch(f);
        String endpoint="/api/v1/internal/platform/execution-snapshot";
        var h=new HttpHeaders();h.setContentType(MediaType.APPLICATION_JSON);
        assertThat(rest.postForEntity(endpoint,new HttpEntity<>(f.task.dispatch(),h),Map.class).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        h.setBearerAuth(jwt.issueUserToken(f.user,"test"));
        assertThat(rest.postForEntity(endpoint,new HttpEntity<>(f.task.dispatch(),h),Map.class).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        h=new HttpHeaders();h.setContentType(MediaType.APPLICATION_JSON);h.set("X-Internal-Token","test-internal-token");
        var response=rest.postForEntity(endpoint,new HttpEntity<>(f.task.dispatch(),h),Map.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).containsEntry("clone_url","https://github.com/team/api").containsEntry("cancel_requested",false);
        String json=(String)response.getBody().get("policy_json");
        String hash=java.util.HexFormat.of().formatHex(digest(json));
        assertThat(response.getBody()).containsEntry("policy_sha256",hash);
        var t=f.task.dispatch();
        var altered=new WorkerTask(1,t.taskId(),t.attempt(),t.fencingToken(),t.organizationId(),t.projectId(),t.repositoryId(),t.commitSha(),t.policyVersion(),t.tokenBudget()+1,t.deadline(),null);
        assertThatThrownBy(()->snapshots.resolve(altered)).hasMessageContaining("differs");
        tasks.cancel(f.user,f.project,f.task.id());
        assertThat(snapshots.resolve(t).cancelRequested()).isTrue();
        coordinator.receive(event(f.task,1,WorkerEvent.Kind.CANCELED,0,0));
        assertThatThrownBy(()->snapshots.resolve(t)).hasMessageContaining("no longer executable");
    }
    private static byte[] digest(String value) {
        try { return java.security.MessageDigest.getInstance("SHA-256").digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8)); }
        catch(java.security.NoSuchAlgorithmException ex) { throw new AssertionError(ex); }
    }

    @Test
    void snapshotRejectsStoredPolicyTamperingAndOldAttempts() {
        var f=fixture();dispatch(f);
        jdbc.update("UPDATE platform_policy_version SET config_json='{}' WHERE id=?",f.task.policyVersion());
        assertThatThrownBy(()->snapshots.resolve(f.task.dispatch())).hasMessageContaining("integrity");
        var retry=fixture();dispatch(retry);expireLease(retry.task.id());coordinator.recover(retry.task.id());
        assertThatThrownBy(()->snapshots.resolve(retry.task.dispatch())).hasMessageContaining("differs");
    }

    @Test
    void artifactRequiresExactDigestAndCurrentAttempt() {
        var f=fixture();start(f);
        var id=UUID.randomUUID().toString();
        assertThatThrownBy(()->artifacts.put(new PlatformArtifactService.Upload(f.task.id(),1,1,id,"0".repeat(64),"{}")))
                .hasMessageContaining("digest");
        var saved=artifacts.put(new PlatformArtifactService.Upload(f.task.id(),1,1,id,digestHex("{}"),"{}"));
        assertThat(saved.sha256()).isEqualTo(digestHex("{}"));
        assertThat(artifacts.put(new PlatformArtifactService.Upload(f.task.id(),1,1,id,digestHex("{}"),"{}"))).isEqualTo(saved);
        assertThatThrownBy(()->artifacts.put(new PlatformArtifactService.Upload(f.task.id(),1,2,UUID.randomUUID().toString(),digestHex("x"),"x")))
                .hasMessageContaining("Stale");
        expireLease(f.task.id());
        assertThatThrownBy(()->artifacts.put(new PlatformArtifactService.Upload(f.task.id(),1,1,id,digestHex("{}"),"{}")))
                .hasMessageContaining("expired");
    }

    @Test
    void successWithoutArtifactCannotSettleBudgetOrAdvanceSequence() {
        var f=fixture();start(f);
        var done=event(f.task,2,WorkerEvent.Kind.SUCCEEDED,30,10);
        assertThatThrownBy(()->coordinator.receive(done)).hasMessageContaining("verified artifact");
        assertThat(tasks.get(f.user,f.project,f.task.id()).lastSequence()).isEqualTo(1);
        assertThat(tasks.budget(f.user,f.org).reservedTokens()).isEqualTo(100);
        artifact(f);
        assertThat(coordinator.receive(done).accepted()).isTrue();
        assertThat(tasks.budget(f.user,f.org).usedTokens()).isEqualTo(40);
    }

    @Test
    void resultRequiresProjectMembershipAndDetectsStoredContentTampering() {
        var f=fixture();start(f);
        assertThatThrownBy(()->artifacts.result(f.user,f.project,f.task.id())).hasMessageContaining("no successful result");
        artifact(f);coordinator.receive(event(f.task,2,WorkerEvent.Kind.SUCCEEDED,30,10));
        String endpoint="/api/v1/platform/projects/"+f.project+"/tasks/"+f.task.id()+"/result";
        var headers=new HttpHeaders();headers.setBearerAuth(jwt.issueUserToken(f.user,"test"));
        var response=rest.exchange(endpoint,HttpMethod.GET,new HttpEntity<>(headers),Map.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).containsEntry("content","{}").containsEntry("sha256",digestHex("{}"));
        var stranger=fixture();
        headers.setBearerAuth(jwt.issueUserToken(stranger.user,"test"));
        assertThat(rest.exchange(endpoint,HttpMethod.GET,new HttpEntity<>(headers),Map.class).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        jdbc.update("DELETE FROM platform_membership WHERE organization_id=? AND user_id=?",f.org,f.user);
        headers.setBearerAuth(jwt.issueUserToken(f.user,"test"));
        assertThat(rest.exchange(endpoint,HttpMethod.GET,new HttpEntity<>(headers),Map.class).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        jdbc.update("INSERT INTO platform_membership(organization_id,user_id,role) VALUES (?,?,'VIEWER')",f.org,f.user);
        jdbc.update("UPDATE platform_task_artifact SET content='tampered' WHERE task_id=?",f.task.id());
        assertThatThrownBy(()->artifacts.result(f.user,f.project,f.task.id())).hasMessageContaining("integrity");
    }

    @Test
    void artifactHttpIngressRequiresPrivateCredential() {
        var f=fixture();start(f);
        String endpoint="/api/v1/internal/platform/artifacts";
        var upload=new PlatformArtifactService.Upload(f.task.id(),1,1,UUID.randomUUID().toString(),digestHex("{}"),"{}");
        var headers=new HttpHeaders();headers.setContentType(MediaType.APPLICATION_JSON);
        assertThat(rest.postForEntity(endpoint,new HttpEntity<>(upload,headers),Map.class).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        headers.setBearerAuth(jwt.issueUserToken(f.user,"test"));
        assertThat(rest.postForEntity(endpoint,new HttpEntity<>(upload,headers),Map.class).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        headers=new HttpHeaders();headers.setContentType(MediaType.APPLICATION_JSON);headers.set("X-Internal-Token","test-internal-token");
        var response=rest.postForEntity(endpoint,new HttpEntity<>(upload,headers),Map.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).containsEntry("sha256",digestHex("{}")).containsEntry("taskId",f.task.id());
    }
    private record Fixture(String user,String org,String project,PlatformTaskService.Task task) { }
    private Fixture fixture() {
        var user=identity.provision("test","worker-"+UUID.randomUUID(),"test-password-123");
        var org=identity.createOrganization(user.id(),"team");
        var project=identity.createProject(user.id(),org.id(),"project");
        var repo=catalog.register(user.id(),project.id(),"api","https://github.com/team/api");
        var policy=catalog.publish(user.id(),project.id(),new PlatformCatalogService.PolicyConfig(4,2,3,2,true,1000,3600));
        tasks.configureBudget("test-admin",org.id(),1000);
        var task=tasks.submit(user.id(),project.id(),"request",new PlatformTaskService.Submission(repo.id(),policy.id(),"a".repeat(40),100));
        return new Fixture(user.id(),org.id(),project.id(),task);
    }
    private WorkerEvent event(PlatformTaskService.Task t,long seq,WorkerEvent.Kind kind,long prompt,long completion) {
        return new WorkerEvent(1,UUID.randomUUID().toString(),t.id(),t.attempt(),t.fencingToken(),seq,kind,Instant.now(),kind==WorkerEvent.Kind.SUCCEEDED?digestHex("{}"):null,prompt,completion);
    }
    private void artifact(Fixture f) {
        artifacts.put(new PlatformArtifactService.Upload(f.task.id(),f.task.attempt(),f.task.fencingToken(),UUID.randomUUID().toString(),digestHex("{}"),"{}"));
    }
    private static String digestHex(String value) { return java.util.HexFormat.of().formatHex(digest(value)); }
    private void dispatch(Fixture f) { assertThat(coordinator.prepareDispatch(f.task.id(),1,1)).isTrue(); }
    private void start(Fixture f) { dispatch(f);coordinator.receive(event(f.task,1,WorkerEvent.Kind.STARTED,0,0)); }
    private void expireLease(String id) { jdbc.update("UPDATE platform_task SET lease_until=? WHERE id=?",Timestamp.from(Instant.now().minusSeconds(1)),id); }

    @Test
    void finalEventsSettleActualUsageExactlyOnceIncludingConcurrentDuplicates() throws Exception {
        var f=fixture();start(f);
        artifact(f);
        var done=event(f.task,2,WorkerEvent.Kind.SUCCEEDED,30,10);
        try(var pool=Executors.newFixedThreadPool(4)) {
            var jobs=IntStream.range(0,8).mapToObj(i -> (Callable<Boolean>) () -> coordinator.receive(done).accepted()).toList();
            int accepted=0;for(var future:pool.invokeAll(jobs)) if(future.get()) accepted++;
            assertThat(accepted).isEqualTo(1);
        }
        var task=tasks.get(f.user,f.project,f.task.id());
        assertThat(task.state()).isEqualTo(TaskState.SUCCEEDED);assertThat(task.settled()).isTrue();
        assertThat(tasks.budget(f.user,f.org)).isEqualTo(new PlatformTaskService.Budget(f.org,1000,0,40));
        assertThat(tasks.reconcile(f.org).consistent()).isTrue();
        assertThat(coordinator.receive(done).accepted()).isFalse();
        assertThatThrownBy(()->coordinator.receive(event(f.task,3,WorkerEvent.Kind.FAILED,30,10))).isInstanceOf(ApiException.class).hasMessageContaining("terminal");
    }

    @Test
    void outOfOrderDecreasingAndOverBudgetEventsCannotChangeStateOrLease() {
        var f=fixture();start(f);
        var before=tasks.get(f.user,f.project,f.task.id());
        assertThatThrownBy(()->coordinator.receive(event(f.task,3,WorkerEvent.Kind.PROGRESS,10,0))).hasMessageContaining("contiguous");
        assertThat(tasks.get(f.user,f.project,f.task.id())).isEqualTo(before);
        coordinator.receive(event(f.task,2,WorkerEvent.Kind.PROGRESS,20,5));
        assertThatThrownBy(()->coordinator.receive(event(f.task,3,WorkerEvent.Kind.PROGRESS,19,5))).hasMessageContaining("monotonic");
        assertThatThrownBy(()->coordinator.receive(event(f.task,3,WorkerEvent.Kind.SUCCEEDED,100,1))).hasMessageContaining("reservation");
        assertThat(tasks.get(f.user,f.project,f.task.id()).lastSequence()).isEqualTo(2);
        assertThat(tasks.budget(f.user,f.org).reservedTokens()).isEqualTo(100);
    }

    @Test
    void aReusedEventIdWithDifferentDataIsRejected() {
        var f=fixture();start(f);
        var progress=event(f.task,2,WorkerEvent.Kind.PROGRESS,10,0);coordinator.receive(progress);
        var changed=new WorkerEvent(1,progress.eventId(),f.task.id(),1,1,2,WorkerEvent.Kind.PROGRESS,progress.occurredAt(),null,11,0);
        assertThatThrownBy(()->coordinator.receive(changed)).hasMessageContaining("reused");
        assertThat(tasks.get(f.user,f.project,f.task.id()).promptTokens()).isEqualTo(10);
    }

    @Test
    void cancellationRacingSuccessSettlesOnceAndHeartbeatCannotExtendCancelLease() {
        var f=fixture();start(f);
        artifact(f);
        var cancel=tasks.cancel(f.user,f.project,f.task.id());
        assertThat(cancel.state()).isEqualTo(TaskState.CANCEL_REQUESTED);
        var progress=coordinator.receive(event(f.task,2,WorkerEvent.Kind.PROGRESS,10,0));
        assertThat(progress.cancelRequested()).isTrue();
        assertThat(progress.task().leaseUntil()).isEqualTo(cancel.leaseUntil());
        coordinator.receive(event(f.task,3,WorkerEvent.Kind.SUCCEEDED,20,5));
        assertThat(tasks.cancel(f.user,f.project,f.task.id()).state()).isEqualTo(TaskState.SUCCEEDED);
        assertThat(tasks.budget(f.user,f.org).usedTokens()).isEqualTo(25);
        assertThat(tasks.reconcile(f.org).consistent()).isTrue();
    }

    @Test
    void anUnstartedCanceledWorkerCannotClaimProgressOrSpending() {
        var f=fixture();dispatch(f);tasks.cancel(f.user,f.project,f.task.id());
        assertThatThrownBy(()->coordinator.receive(event(f.task,1,WorkerEvent.Kind.PROGRESS,0,0))).hasMessageContaining("claim STARTED");
        assertThatThrownBy(()->coordinator.receive(event(f.task,1,WorkerEvent.Kind.CANCELED,1,0))).hasMessageContaining("claim STARTED");
        coordinator.receive(event(f.task,1,WorkerEvent.Kind.CANCELED,0,0));
        assertThat(tasks.budget(f.user,f.org).availableTokens()).isEqualTo(1000);
    }

    @Test
    void unclaimedDispatchIsRetriedWithNewAttemptAndRejectsTheOldWorker() {
        var f=fixture();dispatch(f);expireLease(f.task.id());
        assertThat(coordinator.recoveryCandidates(100)).contains(f.task.id());
        assertThat(coordinator.recover(f.task.id())).isTrue();
        var retry=tasks.get(f.user,f.project,f.task.id());
        assertThat(retry.state()).isEqualTo(TaskState.QUEUED);assertThat(retry.attempt()).isEqualTo(2);assertThat(retry.fencingToken()).isEqualTo(2);
        assertThat(coordinator.prepareDispatch(retry.id(),1,1)).isFalse();
        assertThatThrownBy(()->coordinator.receive(event(f.task,1,WorkerEvent.Kind.STARTED,0,0))).hasMessageContaining("Stale worker");
        assertThat(coordinator.prepareDispatch(retry.id(),2,2)).isTrue();
        coordinator.receive(event(retry,1,WorkerEvent.Kind.STARTED,0,0));
        assertThat(tasks.get(f.user,f.project,retry.id()).state()).isEqualTo(TaskState.RUNNING);
        assertThat(tasks.budget(f.user,f.org).reservedTokens()).isEqualTo(100);
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_outbox WHERE task_id=? AND kind='DISPATCH'",Integer.class,retry.id())).isEqualTo(2);
    }

    @Test
    void exhaustedUnclaimedDispatchesRefundWithoutRestartingForever() {
        var f=fixture();
        for(int attempt=1;attempt<=3;attempt++) {
            assertThat(coordinator.prepareDispatch(f.task.id(),attempt,attempt)).isTrue();
            expireLease(f.task.id());assertThat(coordinator.recover(f.task.id())).isTrue();
        }
        var terminal=tasks.get(f.user,f.project,f.task.id());
        assertThat(terminal.state()).isEqualTo(TaskState.FAILED);
        assertThat(terminal.recoveryReason()).isEqualTo("DISPATCH_ATTEMPTS_EXHAUSTED");
        assertThat(tasks.budget(f.user,f.org).availableTokens()).isEqualTo(1000);
        assertThat(coordinator.recover(f.task.id())).isFalse();
    }

    @Test
    void lostRunningWorkerChargesTheReservationConservativelyAndCannotOverwrite() {
        var f=fixture();start(f);coordinator.receive(event(f.task,2,WorkerEvent.Kind.PROGRESS,20,0));
        expireLease(f.task.id());coordinator.recover(f.task.id());
        var terminal=tasks.get(f.user,f.project,f.task.id());
        assertThat(terminal.state()).isEqualTo(TaskState.FAILED);
        assertThat(terminal.recoveryReason()).isEqualTo("WORKER_LOST_USAGE_UNCERTAIN");
        assertThat(tasks.budget(f.user,f.org)).isEqualTo(new PlatformTaskService.Budget(f.org,1000,0,100));
        assertThat(tasks.reconcile(f.org).consistent()).isTrue();
        assertThatThrownBy(()->coordinator.receive(event(f.task,3,WorkerEvent.Kind.SUCCEEDED,30,10))).hasMessageContaining("Stale worker");
        assertThat(coordinator.recover(f.task.id())).isFalse();
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_budget_ledger WHERE task_id=? AND kind='SETTLE'",Integer.class,f.task.id())).isEqualTo(1);
    }

    @Test
    void queuedDeadlineRefundsAndAnExpiredLeaseCannotBeRevivedByHeartbeat() {
        var queued=fixture();
        jdbc.update("UPDATE platform_task SET deadline=? WHERE id=?",Timestamp.from(Instant.now().minusSeconds(1)),queued.task.id());
        assertThat(coordinator.prepareDispatch(queued.task.id(),1,1)).isFalse();
        coordinator.recover(queued.task.id());
        assertThat(tasks.get(queued.user,queued.project,queued.task.id()).state()).isEqualTo(TaskState.CANCELED);
        assertThat(tasks.budget(queued.user,queued.org).usedTokens()).isZero();
        var running=fixture();start(running);expireLease(running.task.id());
        assertThatThrownBy(()->coordinator.receive(event(running.task,2,WorkerEvent.Kind.PROGRESS,1,0))).hasMessageContaining("expired");
        assertThat(tasks.get(running.user,running.project,running.task.id()).lastSequence()).isEqualTo(1);
    }

    @Test
    void internalIngressIsStrictAndPublicReplayEnforcesProjectMembership() {
        var f=fixture();dispatch(f);
        var started=event(f.task,1,WorkerEvent.Kind.STARTED,0,0);
        var h=new HttpHeaders();h.setContentType(MediaType.APPLICATION_JSON);
        String ingress="/api/v1/internal/platform/events";
        assertThat(rest.postForEntity(ingress,new HttpEntity<>(started,h),Map.class).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        h.set("X-Internal-Token","test-internal-token");
        assertThat(rest.postForEntity(ingress,new HttpEntity<>(Map.of("schema_version",1,"unexpected",true),h),Map.class).getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(rest.postForEntity(ingress,new HttpEntity<>(started,h),Map.class).getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(rest.postForEntity(ingress,new HttpEntity<>(started,h),Map.class).getBody()).containsEntry("accepted",false);
        coordinator.receive(event(f.task,2,WorkerEvent.Kind.FAILED,10,1));
        String replay="/api/v1/platform/projects/"+f.project+"/tasks/"+f.task.id()+"/events";
        h=new HttpHeaders();h.setBearerAuth(jwt.issueUserToken(f.user,"test"));
        var first=rest.exchange(replay+"?limit=2",HttpMethod.GET,new HttpEntity<>(h),Map.class);
        assertThat(first.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat((java.util.List<?>)first.getBody().get("items")).hasSize(2);
        long cursor=((Number)first.getBody().get("nextCursor")).longValue();
        var second=coordinator.events(f.user,f.project,f.task.id(),cursor,100);
        assertThat(second.items()).hasSize(2);assertThat(second.nextCursor()).isNull();
        assertThat(second.items().stream().map(PlatformWorkerCoordinator.Event::id)).allMatch(id->id>cursor);
        var other=fixture();
        assertThatThrownBy(()->coordinator.events(other.user,f.project,f.task.id(),0,50)).isInstanceOf(ApiException.class);
        assertThatThrownBy(()->coordinator.events(f.user,f.project,f.task.id(),-1,50)).isInstanceOf(ApiException.class);
    }

    @Test
    void repairApprovalBindsSourceAndPatchAndVerificationIsIdempotent() {
        var f=fixture();start(f);artifact(f);coordinator.receive(event(f.task,2,WorkerEvent.Kind.SUCCEEDED,30,10));
        String patch="diff --git a/Demo.java b/Demo.java\n+fixed\n";
        String patchSha=digestHex(patch);
        var proposal=reviews.propose(f.user,f.project,f.task.id(),new PlatformRepairReviewService.ProposalRequest(f.task.commitSha(),patchSha,patch,"mvn -q -DskipTests=false test"));
        assertThat(proposal.status()).isEqualTo(PlatformRepairReviewService.Status.AWAITING_APPROVAL);
        assertThat(reviews.propose(f.user,f.project,f.task.id(),new PlatformRepairReviewService.ProposalRequest(f.task.commitSha(),patchSha,patch,"mvn -q -DskipTests=false test"))).isEqualTo(proposal);
        assertThatThrownBy(()->reviews.approve(f.user,f.project,f.task.id(),proposal.id(),"0".repeat(64))).hasMessageContaining("digest");
        var approved=reviews.approve(f.user,f.project,f.task.id(),proposal.id(),proposal.approvalDigest());
        assertThat(approved.status()).isEqualTo(PlatformRepairReviewService.Status.APPROVED);
        String evidence="{\"review_id\":\""+proposal.id()+"\",\"task_id\":\""+f.task.id()+"\",\"source_commit_sha\":\""+f.task.commitSha()+"\",\"patch_sha256\":\""+patchSha+"\",\"test_command\":\"mvn -q -DskipTests=false test\",\"baseline_exit_code\":1,\"regression_exit_code\":0,\"baseline_failure_contains\":\"AssertionError\",\"baseline_output\":\"AssertionError\",\"status\":\"regression_passed\"}";
        var verification=new PlatformRepairReviewService.VerificationRequest("worker-123",proposal.approvalDigest(),digestHex(evidence),true,evidence);
        var passed=reviews.verify(f.project,f.task.id(),proposal.id(),verification);
        assertThat(passed.status()).isEqualTo(PlatformRepairReviewService.Status.PASSED);
        assertThat(reviews.verify(f.project,f.task.id(),proposal.id(),verification)).isEqualTo(passed);
        assertThatThrownBy(()->reviews.verify(f.project,f.task.id(),proposal.id(),new PlatformRepairReviewService.VerificationRequest("worker-124",proposal.approvalDigest(),digestHex("other"),true,"other"))).hasMessageContaining("valid JSON");
    }
}
