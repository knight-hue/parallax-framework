package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;

import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.parallax.gateway.auth.JwtService;
import dev.parallax.gateway.platform.*;
import dev.parallax.gateway.task.TaskState;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

/** Separate Python process, real HTTP in both directions; source/model are deterministic fixtures. */
@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT, properties={
    "parallax.gateway.require-auth=true", "parallax.ratelimit.enabled=false",
    "parallax.jwt.secret=0123456789abcdef0123456789abcdef",
    "parallax.gateway.admin-secret=platform-test-admin"
})
@ActiveProfiles("test")
@EnabledIfSystemProperty(named="parallax.test.python", matches=".+")
class PlatformWorkerProcessIT {
    @LocalServerPort int gatewayPort;
    @Autowired PlatformIdentityService identity;
    @Autowired PlatformCatalogService catalog;
    @Autowired PlatformTaskService tasks;
    @Autowired PlatformWorkerCoordinator coordinator;
    @Autowired PlatformArtifactService artifacts;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper mapper;
    @Autowired JwtService jwt;
    @TempDir Path temporary;
    private final HttpClient http=HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(2)).build();

    private record Fixture(String user,String org,String project,PlatformTaskService.Task task) {}
    private Fixture fixture(String sha) {
        var user=identity.provision("test","process-"+UUID.randomUUID(),"test-password-123");
        var org=identity.createOrganization(user.id(),"team");
        var project=identity.createProject(user.id(),org.id(),"project");
        var repository=catalog.register(user.id(),project.id(),"api","https://github.com/team/api");
        var policy=catalog.publish(user.id(),project.id(),new PlatformCatalogService.PolicyConfig(2,2,1,2,false,1000,600));
        tasks.configureBudget("test",org.id(),2000);
        var task=tasks.submit(user.id(),project.id(),"request",new PlatformTaskService.Submission(repository.id(),policy.id(),sha,1000));
        assertThat(coordinator.prepareDispatch(task.id(),1,1)).isTrue();
        return new Fixture(user.id(),org.id(),project.id(),task);
    }
    private Process start(int port) throws Exception {
        Path repo=Path.of("").toAbsolutePath().getParent();
        var builder=new ProcessBuilder(System.getProperty("parallax.test.python"),
            repo.resolve("backend/tests/platform_process_fixture.py").toString(), temporary.toString(),
            "http://127.0.0.1:"+gatewayPort,Integer.toString(port));
        builder.directory(repo.resolve("backend").toFile());
        builder.environment().put("PYTHONPATH",repo.resolve("backend").toString());
        for(String key:new String[]{"OPENAI_API_KEY","PARALLAX_LLM_API_KEY","OPENAI_BASE_URL","PARALLAX_LLM_BASE_URL"}) builder.environment().remove(key);
        return builder.redirectErrorStream(true).redirectOutput(ProcessBuilder.Redirect.appendTo(temporary.resolve("worker.log").toFile())).start();
    }
    private void ready(Process process,int port) throws Exception {
        await(()->{
            assertThat(process.isAlive()).as("Python process must remain alive; see %s",temporary.resolve("worker.log")).isTrue();
            try { return http.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+"/health")).timeout(Duration.ofSeconds(1)).GET().build(),HttpResponse.BodyHandlers.discarding()).statusCode()==200; }
            catch(Exception ex) { return false; }
        });
    }
    private static void await(BooleanSupplier condition) throws Exception {
        long end=System.nanoTime()+Duration.ofSeconds(25).toNanos();
        while(System.nanoTime()<end) { if(condition.getAsBoolean()) return;Thread.sleep(50); }
        assertThat(condition.getAsBoolean()).as("Condition must converge within 25 seconds").isTrue();
    }
    private static void stop(Process process) throws Exception {
        process.destroy();
        if(!process.waitFor(5,TimeUnit.SECONDS)) { process.destroyForcibly();assertThat(process.waitFor(5,TimeUnit.SECONDS)).isTrue(); }
    }
    private PlatformTaskService.Task current(Fixture f) { return tasks.get(f.user,f.project,f.task.id()); }

    @Test void realHttpExecutionPersistsReportAndRestartCannotDuplicateSpending() throws Exception {
        int port;try(var socket=new ServerSocket(0,1,java.net.InetAddress.getByName("127.0.0.1"))) {port=socket.getLocalPort();}
        Process process=start(port);
        try {
            ready(process,port);
            var bridge=new WorkerHttpBridge("http://127.0.0.1:"+port,"test-internal-token");
            var f=fixture("a".repeat(40));
            String wire=mapper.writeValueAsString(f.task.dispatch());
            assertThat(bridge.deliver("DISPATCH",wire)).isEqualTo(WorkerHttpBridge.Delivery.ACK);
            assertThat(bridge.deliver("DISPATCH",wire)).isEqualTo(WorkerHttpBridge.Delivery.ACK);
            await(()->current(f).state()==TaskState.SUCCEEDED);
            assertThat(current(f).lastSequence()).isGreaterThan(2);
            assertThat(tasks.budget(f.user,f.org)).isEqualTo(new PlatformTaskService.Budget(f.org,2000,0,10));
            assertThat(tasks.reconcile(f.org).consistent()).isTrue();
            var result=artifacts.result(f.user,f.project,f.task.id());
            assertThat(mapper.readTree(result.content()).path("manifest").path("run_id").asText()).isEqualTo(f.task.id());
            assertThat(result.content()).contains("Demo.java","Empty array access");
            String endpoint="http://127.0.0.1:"+gatewayPort+"/api/v1/platform/projects/"+f.project+"/tasks/"+f.task.id()+"/result";
            var request=HttpRequest.newBuilder(URI.create(endpoint)).header("Authorization","Bearer "+jwt.issueUserToken(f.user,"test")).GET().build();
            assertThat(http.send(request,HttpResponse.BodyHandlers.ofString()).statusCode()).isEqualTo(200);
            var stranger=identity.provision("test","stranger-"+UUID.randomUUID(),"test-password-123");
            var denied=HttpRequest.newBuilder(URI.create(endpoint)).header("Authorization","Bearer "+jwt.issueUserToken(stranger.id(),"test")).GET().build();
            assertThat(http.send(denied,HttpResponse.BodyHandlers.discarding()).statusCode()).isEqualTo(404);
            long sequence=current(f).lastSequence();
            stop(process);process=start(port);ready(process,port);
            assertThat(bridge.deliver("DISPATCH",wire)).isEqualTo(WorkerHttpBridge.Delivery.ACK);
            assertThat(current(f).lastSequence()).isEqualTo(sequence);
            assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM platform_budget_ledger WHERE task_id=? AND kind='SETTLE'",Integer.class,f.task.id())).isEqualTo(1);

            var canceled=fixture("b".repeat(40));
            assertThat(bridge.deliver("DISPATCH",mapper.writeValueAsString(canceled.task.dispatch()))).isEqualTo(WorkerHttpBridge.Delivery.ACK);
            await(()->current(canceled).lastSequence()>1);
            tasks.cancel(canceled.user,canceled.project,canceled.task.id());
            assertThat(bridge.deliver("CANCEL",mapper.writeValueAsString(canceled.task.dispatch()))).isEqualTo(WorkerHttpBridge.Delivery.ACK);
            stop(process);
            jdbc.update("UPDATE platform_task SET lease_until=? WHERE id=?",Timestamp.from(Instant.now().minusSeconds(1)),canceled.task.id());
            assertThat(coordinator.recover(canceled.task.id())).isTrue();
            assertThat(current(canceled).recoveryReason()).isEqualTo("WORKER_LOST_USAGE_UNCERTAIN");
            assertThat(tasks.budget(canceled.user,canceled.org)).isEqualTo(new PlatformTaskService.Budget(canceled.org,2000,0,1000));
            assertThat(tasks.reconcile(canceled.org).consistent()).isTrue();
        } finally {
            if(process.isAlive()) stop(process);
            if(Files.exists(temporary.resolve("worker.log"))) Files.copy(temporary.resolve("worker.log"),Path.of("target/platform-worker-process.log"),java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
    }
}
