package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.net.InetSocketAddress;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;
import com.sun.net.httpserver.HttpServer;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.rabbitmq.client.Channel;
import dev.parallax.gateway.platform.*;
import dev.parallax.gateway.task.WorkerTask;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;

class WorkerHttpBridgeTest {
    private String payload() throws Exception {
        var task=new WorkerTask(1,"task",1,1,"org","project","repository","a".repeat(40),"policy",100,Instant.now().plusSeconds(3600),null);
        return JsonMapper.builder().addModule(new JavaTimeModule()).disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS).build().writeValueAsString(task);
    }
    private Message message(String payload) {
        var props=new MessageProperties();props.setDeliveryTag(42);props.setReceivedRoutingKey("task");props.setHeader("kind","DISPATCH");
        return new Message(payload.getBytes(java.nio.charset.StandardCharsets.UTF_8),props);
    }
    @Test void httpClassifiesAcceptedStaleTransientAndPermanentFailures() throws Exception {
        var status=new AtomicInteger(202);var calls=new AtomicInteger();
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        String json=payload();
        server.createContext("/api/v1/platform-worker/execute",exchange->{
            calls.incrementAndGet();
            assertThat(exchange.getRequestHeaders().getFirst("X-Internal-Token")).isEqualTo("test-token");
            assertThat(new String(exchange.getRequestBody().readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).isEqualTo(json);
            exchange.sendResponseHeaders(status.get(),-1);exchange.close();
        });server.start();
        try {
            var bridge=new WorkerHttpBridge("http://127.0.0.1:"+server.getAddress().getPort(),"test-token");
            for(int code:new int[]{202,409,410}) {status.set(code);assertThat(bridge.deliver("DISPATCH",json)).isEqualTo(WorkerHttpBridge.Delivery.ACK);}
            for(int code:new int[]{429,500,503}) {status.set(code);assertThat(bridge.deliver("DISPATCH",json)).isEqualTo(WorkerHttpBridge.Delivery.RETRY);}
            for(int code:new int[]{400,401,403,404,422}) {status.set(code);assertThat(bridge.deliver("DISPATCH",json)).isEqualTo(WorkerHttpBridge.Delivery.DEAD_LETTER);}
            int before=calls.get();
            assertThat(bridge.deliver("DISPATCH","{\"unexpected\":true}")).isEqualTo(WorkerHttpBridge.Delivery.DEAD_LETTER);
            assertThat(calls.get()).isEqualTo(before);
        } finally {server.stop(0);}
    }
    @Test void manualBrokerAcknowledgementFollowsWorkerResponse() throws Exception {
        var status=new AtomicInteger(202);
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/api/v1/platform-worker/execute",e->{e.getRequestBody().readAllBytes();e.sendResponseHeaders(status.get(),-1);e.close();});server.start();
        try {
            var listener=new RabbitWorkerListener(new WorkerHttpBridge("http://127.0.0.1:"+server.getAddress().getPort(),"test-token"),new SimpleMeterRegistry());
            Channel channel=mock(Channel.class);listener.onMessage(message(payload()),channel);verify(channel).basicAck(42,false);
            reset(channel);status.set(503);listener.onMessage(message(payload()),channel);verify(channel).basicNack(42,false,true);
            reset(channel);status.set(401);listener.onMessage(message(payload()),channel);verify(channel).basicReject(42,false);
            reset(channel);var poisoned=message("{}");poisoned.getMessageProperties().setHeader("kind","CANCEL");listener.onMessage(poisoned,channel);verify(channel).basicReject(42,false);
        } finally {server.stop(0);}
    }
}
