package dev.parallax.gateway.platform;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

public final class RabbitDispatchTransport implements DispatchTransport {
    private final RabbitTemplate rabbit;
    private final String exchange;
    private final int timeoutMs;
    public RabbitDispatchTransport(RabbitTemplate rabbit,String exchange,int timeoutMs) {
        if(timeoutMs<100 || timeoutMs>10000) throw new IllegalArgumentException("Broker confirm timeout must be 100..10000 ms");
        this.rabbit=rabbit;this.exchange=exchange;this.timeoutMs=timeoutMs;
        rabbit.setMandatory(true);
    }
    @Override
    public void publish(PlatformOutboxStore.Claim claim) throws Exception {
        String route=switch(claim.kind()) { case "DISPATCH" -> "task";case "CANCEL" -> "cancel";default -> throw new IllegalArgumentException("Unsupported dispatch kind"); };
        var props=new MessageProperties();
        props.setContentType(MessageProperties.CONTENT_TYPE_JSON);props.setContentEncoding("UTF-8");
        props.setDeliveryMode(MessageDeliveryMode.PERSISTENT);props.setMessageId(claim.id());props.setCorrelationId(claim.taskId());
        props.setHeader("schema_version",1);props.setHeader("kind",claim.kind());
        var data=new CorrelationData(claim.id());
        rabbit.send(exchange,route,new Message(claim.payload().getBytes(StandardCharsets.UTF_8),props),data);
        var confirm=data.getFuture().get(timeoutMs,TimeUnit.MILLISECONDS);
        if(!confirm.isAck() || data.getReturned()!=null) throw new IllegalStateException("Broker did not confirm routable delivery");
    }
}
