package dev.parallax.gateway;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import java.util.concurrent.TimeoutException;
import dev.parallax.gateway.platform.PlatformOutboxStore;
import dev.parallax.gateway.platform.RabbitDispatchTransport;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

class RabbitDispatchTransportTest {
    private PlatformOutboxStore.Claim claim() { return new PlatformOutboxStore.Claim("message-id","task-id",1,"DISPATCH","{}","claim-token",1); }
    @Test void waitsForConfirmationAndPreservesPersistentMessageIdentity() throws Exception {
        var rabbit=mock(RabbitTemplate.class);
        doAnswer(invocation->{
            Message message=invocation.getArgument(2);
            assertThat(message.getMessageProperties().getDeliveryMode()).isEqualTo(MessageDeliveryMode.PERSISTENT);
            assertThat(message.getMessageProperties().getMessageId()).isEqualTo("message-id");
            assertThat(message.getMessageProperties().getContentType()).isEqualTo("application/json");
            assertThat(message.getMessageProperties().getHeader("kind").toString()).isEqualTo("DISPATCH");
            CorrelationData data=invocation.getArgument(3);data.getFuture().complete(new CorrelationData.Confirm(true,null));return null;
        }).when(rabbit).send(eq("exchange"),eq("task"),any(Message.class),any(CorrelationData.class));
        new RabbitDispatchTransport(rabbit,"exchange",100).publish(claim());
        verify(rabbit).setMandatory(true);
    }
    @Test void nackAndUnroutableReturnsAreNeverRecordedAsSuccess() {
        for(boolean unroutable:new boolean[]{false,true}) {
            var rabbit=mock(RabbitTemplate.class);
            doAnswer(invocation->{
                CorrelationData data=invocation.getArgument(3);
                if(unroutable) data.setReturned(new ReturnedMessage(invocation.getArgument(2),312,"NO_ROUTE","exchange","task"));
                data.getFuture().complete(new CorrelationData.Confirm(unroutable,unroutable?null:"nack"));return null;
            }).when(rabbit).send(anyString(),anyString(),any(Message.class),any(CorrelationData.class));
            assertThatThrownBy(()->new RabbitDispatchTransport(rabbit,"exchange",100).publish(claim())).hasMessageContaining("routable delivery");
        }
    }
    @Test void missingConfirmationTimesOutWithAReclaimableOutbox() {
        var rabbit=mock(RabbitTemplate.class);
        assertThatThrownBy(()->new RabbitDispatchTransport(rabbit,"exchange",100).publish(claim())).isInstanceOf(TimeoutException.class);
    }
}
