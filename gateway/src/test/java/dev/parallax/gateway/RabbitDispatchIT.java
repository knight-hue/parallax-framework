package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;
import java.net.InetSocketAddress;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import com.sun.net.httpserver.HttpServer;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import dev.parallax.gateway.platform.*;
import dev.parallax.gateway.task.WorkerTask;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.CachingConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.listener.SimpleMessageListenerContainer;

/** Opt-in, isolated broker only. The native verification tool supplies a temporary broker URI. */
@EnabledIfSystemProperty(named="parallax.test.rabbit",matches="true")
class RabbitDispatchIT {
    CachingConnectionFactory factory;
    RabbitAdmin admin;
    RabbitTemplate template;
    String exchange,queue,deadExchange,deadQueue;
    @BeforeEach void setup() throws Exception {
        String uri=System.getenv("PARALLAX_TEST_RABBIT_URI");
        if(uri==null || !"true".equals(System.getenv("PARALLAX_TEST_RABBIT_ISOLATED"))) throw new IllegalStateException("An isolated test broker is required");
        factory=new CachingConnectionFactory(java.net.URI.create(uri));
        factory.setPublisherConfirmType(CachingConnectionFactory.ConfirmType.CORRELATED);factory.setPublisherReturns(true);
        factory.getRabbitConnectionFactory().setConnectionTimeout(3000);
        try(var direct=factory.getRabbitConnectionFactory().newConnection()) {
            assertThat(direct.getServerProperties().get("product").toString()).isEqualTo("RabbitMQ");
            System.out.println("Verified broker: RabbitMQ "+direct.getServerProperties().get("version"));
        }
        exchange="parallax-it-"+UUID.randomUUID();queue=exchange+".task";deadExchange=exchange+".dead";deadQueue=exchange+".dead.queue";
        admin=new RabbitAdmin(factory);template=new RabbitTemplate(factory);
        admin.declareExchange(new DirectExchange(exchange,true,false));admin.declareExchange(new DirectExchange(deadExchange,true,false));
        admin.declareQueue(QueueBuilder.durable(queue).withArgument("x-queue-type","quorum").withArgument("x-delivery-limit",10).deadLetterExchange(deadExchange).deadLetterRoutingKey("dead").build());
        admin.declareQueue(QueueBuilder.durable(deadQueue).withArgument("x-queue-type","quorum").build());
        admin.declareBinding(new Binding(queue,Binding.DestinationType.QUEUE,exchange,"task",null));
        admin.declareBinding(new Binding(deadQueue,Binding.DestinationType.QUEUE,deadExchange,"dead",null));
    }
    @AfterEach void cleanup() {
        if(admin!=null) {
            if(queue!=null) admin.deleteQueue(queue);if(deadQueue!=null) admin.deleteQueue(deadQueue);
            if(exchange!=null) admin.deleteExchange(exchange);if(deadExchange!=null) admin.deleteExchange(deadExchange);
        }
        if(factory!=null) factory.destroy();
    }
    private PlatformOutboxStore.Claim claim(String kind) throws Exception {
        var task=new WorkerTask(1,"task",1,1,"org","project","repo","a".repeat(40),"policy",100,Instant.now().plusSeconds(3600),null);
        String json=JsonMapper.builder().addModule(new JavaTimeModule()).disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS).build().writeValueAsString(task);
        return new PlatformOutboxStore.Claim(UUID.randomUUID().toString(),"task",1,kind,json,"claim",1);
    }
    @Test void durableConfirmationAndChannelLossCauseBrokerRedelivery() throws Exception {
        var claim=claim("DISPATCH");new RabbitDispatchTransport(template,exchange,5000).publish(claim);
        var connection=factory.createConnection();
        try {
            var channel=connection.createChannel(false);
            var received=channel.basicGet(queue,false);
            assertThat(received).isNotNull();assertThat(received.getProps().getDeliveryMode()).isEqualTo(2);
            assertThat(received.getProps().getMessageId()).isEqualTo(claim.id());
            // Abort the underlying channel, bypassing the CachingConnectionFactory logical-close cache.
            ((org.springframework.amqp.rabbit.connection.ChannelProxy)channel).getTargetChannel().abort();
            var recovered=connection.createChannel(false);
            com.rabbitmq.client.GetResponse redelivered=null;
            for(int i=0;i<100 && redelivered==null;i++) { redelivered=recovered.basicGet(queue,false);if(redelivered==null) Thread.sleep(20); }
            assertThat(redelivered).isNotNull();assertThat(redelivered.getEnvelope().isRedeliver()).isTrue();
            recovered.basicAck(redelivered.getEnvelope().getDeliveryTag(),false);recovered.close();
        } finally {connection.close();}
    }
    @Test void mandatoryUnroutableMessageIsNeverAcknowledgedAsPublished() throws Exception {
        assertThatThrownBy(()->new RabbitDispatchTransport(template,exchange,5000).publish(claim("CANCEL"))).hasMessageContaining("routable delivery");
    }
    @Test void permanentWorkerFailureIsManuallyRejectedToTheDeadLetterQueue() throws Exception {
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/api/v1/platform-worker/execute",e->{e.getRequestBody().readAllBytes();e.sendResponseHeaders(401,-1);e.close();});server.start();
        var listener=new SimpleMessageListenerContainer(factory);
        listener.setQueueNames(queue);listener.setAcknowledgeMode(AcknowledgeMode.MANUAL);listener.setPrefetchCount(1);
        listener.setMessageListener(new RabbitWorkerListener(new WorkerHttpBridge("http://127.0.0.1:"+server.getAddress().getPort(),"test-token"),new SimpleMeterRegistry()));
        try {
            listener.afterPropertiesSet();listener.start();
            new RabbitDispatchTransport(template,exchange,5000).publish(claim("DISPATCH"));
            var dead=template.receive(deadQueue,10000);
            assertThat(dead).isNotNull();assertThat(dead.getMessageProperties().getHeaders()).containsKey("x-death");
            assertThat(template.receive(queue)).isNull();
        } finally {listener.stop();server.stop(0);}
    }

    /** Two sequential worker processes on one port: the bridge must retry a 5xx, then accept the recovery delivery. */
    @Test void transientWorkerFailureRequeuesAndASecondDeliverySucceeds() throws Exception {
        var attempts=new AtomicInteger();
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/api/v1/platform-worker/execute",e->{
            e.getRequestBody().readAllBytes();e.sendResponseHeaders(attempts.incrementAndGet()==1?503:200,-1);e.close();
        });
        server.start();
        var registry=new SimpleMeterRegistry();
        var listener=startListener(new WorkerHttpBridge("http://127.0.0.1:"+server.getAddress().getPort(),"test-token"),registry);
        try {
            new RabbitDispatchTransport(template,exchange,5000).publish(claim("DISPATCH"));
            assertThat(awaitCount(()->deliveries(registry,"RETRY"),1)).isTrue();
            assertThat(awaitCount(()->deliveries(registry,"ACK"),1)).isTrue();
            assertThat(attempts.get()).isEqualTo(2);
            assertThat(template.receive(queue,500)).isNull();
            assertThat(template.receive(deadQueue,500)).isNull();
        } finally {listener.stop();server.stop(0);}
    }

    /** The first worker process is killed mid-task; deliveries fail to connect until a new process binds the port. */
    @Test void workerProcessDeathKeepsRetryingUntilARestartedWorkerAccepts() throws Exception {
        var port=new AtomicInteger();
        var first=new AtomicInteger();
        var dying=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        dying.createContext("/api/v1/platform-worker/execute",e->{
            e.getRequestBody().readAllBytes();first.incrementAndGet();e.sendResponseHeaders(503,-1);e.close();
        });
        dying.start();port.set(dying.getAddress().getPort());
        var registry=new SimpleMeterRegistry();
        var listener=startListener(new WorkerHttpBridge("http://127.0.0.1:"+port.get(),"test-token"),registry);
        HttpServer revived=null;
        try {
            new RabbitDispatchTransport(template,exchange,5000).publish(claim("DISPATCH"));
            assertThat(awaitCount(()->deliveries(registry,"RETRY"),1)).isTrue();
            dying.stop(0);
            assertThat(awaitCount(()->deliveries(registry,"RETRY"),2)).isTrue();
            revived=rebind(port.get());
            assertThat(awaitCount(()->deliveries(registry,"ACK"),1)).isTrue();
            // Requeue loops are fast, so the dying worker may still see a few redeliveries before the socket closes.
            assertThat(first.get()).isGreaterThanOrEqualTo(1);
            assertThat(template.receive(queue,500)).isNull();
            assertThat(template.receive(deadQueue,500)).isNull();
        } finally {listener.stop();if(revived!=null) revived.stop(0);dying.stop(0);}
    }

    /** A stale-or-duplicate 409 is a safe acknowledgement, so the broker must not redeliver it. */
    @Test void staleContractIsAcknowledgedAndNeverRedelivered() throws Exception {
        var hits=new AtomicInteger();
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/api/v1/platform-worker/execute",e->{
            e.getRequestBody().readAllBytes();hits.incrementAndGet();e.sendResponseHeaders(409,-1);e.close();
        });
        server.start();
        var registry=new SimpleMeterRegistry();
        var listener=startListener(new WorkerHttpBridge("http://127.0.0.1:"+server.getAddress().getPort(),"test-token"),registry);
        try {
            new RabbitDispatchTransport(template,exchange,5000).publish(claim("DISPATCH"));
            assertThat(awaitCount(()->deliveries(registry,"ACK"),1)).isTrue();
            Thread.sleep(600);
            assertThat(hits.get()).isEqualTo(1);
            assertThat(deliveries(registry,"RETRY")).isZero();
            assertThat(template.receive(queue,300)).isNull();
            assertThat(template.receive(deadQueue,300)).isNull();
        } finally {listener.stop();server.stop(0);}
    }

    private SimpleMessageListenerContainer startListener(WorkerHttpBridge bridge,SimpleMeterRegistry registry) throws Exception {
        var listener=new SimpleMessageListenerContainer(factory);
        listener.setQueueNames(queue);listener.setAcknowledgeMode(AcknowledgeMode.MANUAL);listener.setPrefetchCount(1);
        listener.setMessageListener(new RabbitWorkerListener(bridge,registry));
        listener.afterPropertiesSet();listener.start();
        return listener;
    }

    private static double deliveries(SimpleMeterRegistry registry,String outcome) {
        return registry.counter("parallax.dispatch.delivery","outcome",outcome).count();
    }

    private static boolean awaitCount(java.util.function.DoubleSupplier current,int target) throws InterruptedException {
        long deadline=System.currentTimeMillis()+20000;
        while(System.currentTimeMillis()<deadline) {
            if(current.getAsDouble()>=target) return true;
            Thread.sleep(25);
        }
        return current.getAsDouble()>=target;
    }

    /** A restarted worker process may need a moment before it can bind the same port again. */
    private static HttpServer rebind(int port) throws Exception {
        long deadline=System.currentTimeMillis()+15000;
        Exception last=null;
        while(System.currentTimeMillis()<deadline) {
            try {
                var server=HttpServer.create(new InetSocketAddress("127.0.0.1",port),0);
                server.createContext("/api/v1/platform-worker/execute",e->{e.getRequestBody().readAllBytes();e.sendResponseHeaders(200,-1);e.close();});
                server.start();
                return server;
            } catch(java.net.BindException ex) { last=ex;Thread.sleep(100); }
        }
        throw new IllegalStateException("A restarted worker could not bind port "+port,last);
    }
}
