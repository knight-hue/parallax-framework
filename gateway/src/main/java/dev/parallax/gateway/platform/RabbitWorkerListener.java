package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;
import com.rabbitmq.client.Channel;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.listener.api.ChannelAwareMessageListener;

public final class RabbitWorkerListener implements ChannelAwareMessageListener {
    private final WorkerHttpBridge bridge;
    private final MeterRegistry metrics;
    public RabbitWorkerListener(WorkerHttpBridge bridge,MeterRegistry metrics) { this.bridge=bridge;this.metrics=metrics; }
    @Override
    public void onMessage(Message message,Channel channel) throws Exception {
        long tag=message.getMessageProperties().getDeliveryTag();
        String route=message.getMessageProperties().getReceivedRoutingKey();
        String kind="task".equals(route)?"DISPATCH":"cancel".equals(route)?"CANCEL":"";
        WorkerHttpBridge.Delivery delivery;
        if(message.getBody().length>8000 || kind.isEmpty() || !kind.equals(message.getMessageProperties().getHeader("kind"))) delivery=WorkerHttpBridge.Delivery.DEAD_LETTER;
        else {
            try { delivery=bridge.deliver(kind,new String(message.getBody(),StandardCharsets.UTF_8)); }
            catch(InterruptedException ex) { channel.basicNack(tag,false,true);Thread.currentThread().interrupt();throw ex; }
        }
        switch(delivery) {
            case ACK -> channel.basicAck(tag,false);
            case RETRY -> channel.basicNack(tag,false,true);
            case DEAD_LETTER -> channel.basicReject(tag,false);
        }
        metrics.counter("parallax.dispatch.delivery","outcome",delivery.name()).increment();
    }
}
