package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import dev.parallax.gateway.platform.*;
import dev.parallax.gateway.task.TaskState;
import dev.parallax.gateway.task.WorkerEvent;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(properties="parallax.worker.lease-seconds=121")
@ActiveProfiles("test")
class PlatformOutboxIntegrationTest {
    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired PlatformWorkerCoordinator coordinator;
    @Autowired PlatformOutboxStore store;
    @Autowired JdbcTemplate jdbc;
    private record Fixture(String user,String project,PlatformTaskService.Task task) { }
    @BeforeEach void clearOnlyThisIsolatedTestContextQueue() { jdbc.update("UPDATE platform_outbox SET status='SUPERSEDED',claim_token=NULL,claim_until=NULL"); }
    private Fixture fixture() {
        var user=identity.provision("test","outbox-"+UUID.randomUUID(),"test-password-123");
        var org=identity.createOrganization(user.id(),"team");var project=identity.createProject(user.id(),org.id(),"project");
        var repo=catalog.register(user.id(),project.id(),"api","https://github.com/team/api");
        var policy=catalog.publish(user.id(),project.id(),new PlatformCatalogService.PolicyConfig(4,2,3,2,true,1000,3600));
        tasks.configureBudget("test-admin",org.id(),100);
        return new Fixture(user.id(),project.id(),tasks.submit(user.id(),project.id(),"request",new PlatformTaskService.Submission(repo.id(),policy.id(),"a".repeat(40),100)));
    }
    private PlatformOutboxDispatcher dispatcher(DispatchTransport transport) { return new PlatformOutboxDispatcher(store,coordinator,tasks,transport,new SimpleMeterRegistry()); }

    @Test
    void concurrentPublishersClaimDistinctRowsAndConfirmBeforeMarkingPublished() throws Exception {
        var a=fixture();var b=fixture();
        try(var pool=Executors.newFixedThreadPool(4)) {
            var jobs=IntStream.range(0,8).mapToObj(i -> (Callable<String>) () -> store.claim().map(PlatformOutboxStore.Claim::id).orElse(null)).toList();
            var ids=new java.util.HashSet<String>();int count=0;
            for(var future:pool.invokeAll(jobs)) { String id=future.get();if(id!=null) {count++;ids.add(id);} }
            assertThat(count).isEqualTo(2);assertThat(ids).hasSize(2);
        }
        jdbc.update("UPDATE platform_outbox SET claim_until=? WHERE status='IN_FLIGHT'",Timestamp.from(Instant.now().minusSeconds(1)));
        var sent=new java.util.ArrayList<String>();
        var dispatcher=dispatcher(c->{
            assertThat(jdbc.queryForObject("SELECT status FROM platform_outbox WHERE id=?",String.class,c.id())).isEqualTo("IN_FLIGHT");
            assertThat(tasks.get(a.task.id().equals(c.taskId())?a.user:b.user,a.task.id().equals(c.taskId())?a.project:b.project,c.taskId()).state()).isEqualTo(TaskState.DISPATCHED);
            sent.add(c.taskId());
        });
        assertThat(dispatcher.publishOne()).isTrue();assertThat(dispatcher.publishOne()).isTrue();assertThat(dispatcher.publishOne()).isFalse();
        assertThat(sent).containsExactlyInAnyOrder(a.task.id(),b.task.id());
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_outbox WHERE status='PUBLISHED'",Integer.class)).isEqualTo(2);
    }

    @Test
    void brokerFailureKeepsMessageForRetryAndDoesNotRefundReservation() {
        var f=fixture();
        var dispatcher=dispatcher(c->{throw new java.io.IOException("simulated broker outage");});
        assertThat(dispatcher.publishOne()).isTrue();
        assertThat(jdbc.queryForObject("SELECT status FROM platform_outbox WHERE task_id=?",String.class,f.task.id())).isEqualTo("PENDING");
        assertThat(tasks.budget(f.user,f.task.organizationId()).reservedTokens()).isEqualTo(100);
        assertThat(dispatcher.publishOne()).isFalse();
        jdbc.update("UPDATE platform_outbox SET available_at=? WHERE task_id=?",Timestamp.from(Instant.now().minusSeconds(1)),f.task.id());
        assertThat(dispatcher(c->{}).publishOne()).isTrue();
        assertThat(jdbc.queryForObject("SELECT publish_attempts FROM platform_outbox WHERE task_id=?",Integer.class,f.task.id())).isEqualTo(2);
    }

    @Test
    void expiredClaimCannotOverwriteTheNewPublishersDecision() {
        fixture();var old=store.claim().orElseThrow();
        jdbc.update("UPDATE platform_outbox SET claim_until=? WHERE id=?",Timestamp.from(Instant.now().minusSeconds(1)),old.id());
        var current=store.claim().orElseThrow();
        assertThat(current.claimToken()).isNotEqualTo(old.claimToken());
        assertThat(store.owned(old)).isFalse();assertThat(store.complete(old,true)).isFalse();assertThat(store.retry(old)).isFalse();
        assertThat(store.complete(current,true)).isTrue();
    }

    @Test
    void cancelWhilePublisherIsInFlightCannotResurrectDispatch() {
        var f=fixture();var claim=store.claim().orElseThrow();
        tasks.cancel(f.user,f.project,f.task.id());
        assertThat(coordinator.prepareDispatch(f.task.id(),1,1)).isFalse();
        assertThat(store.owned(claim)).isFalse();assertThat(store.complete(claim,true)).isFalse();
        assertThat(tasks.budget(f.user,f.task.organizationId()).reservedTokens()).isZero();
        assertThat(dispatcher(c->{throw new AssertionError("Must not publish canceled work");}).publishOne()).isFalse();
    }

    @Test
    void dispatchAlreadyClaimedByWorkerIsSupersededInsteadOfStartingAgain() {
        var f=fixture();coordinator.prepareDispatch(f.task.id(),1,1);
        coordinator.receive(new WorkerEvent(1,UUID.randomUUID().toString(),f.task.id(),1,1,1,WorkerEvent.Kind.STARTED,Instant.now(),null,0,0));
        assertThat(dispatcher(c->{throw new AssertionError("Must not republish running work");}).publishOne()).isTrue();
        assertThat(jdbc.queryForObject("SELECT status FROM platform_outbox WHERE task_id=?",String.class,f.task.id())).isEqualTo("SUPERSEDED");
    }
}
