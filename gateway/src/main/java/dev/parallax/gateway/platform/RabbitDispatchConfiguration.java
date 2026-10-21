package dev.parallax.gateway.platform;

import java.net.URI;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.CachingConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.listener.SimpleMessageListenerContainer;

@Configuration
@EnableScheduling
@ConditionalOnProperty(name="parallax.dispatch.enabled",havingValue="true")
public class RabbitDispatchConfiguration {
    public static final String EXCHANGE="parallax.dispatch.v1";
    public static final String TASK_QUEUE="parallax.dispatch.v1.task";
    public static final String CANCEL_QUEUE="parallax.dispatch.v1.cancel";
    public static final String DEAD_QUEUE="parallax.dispatch.v1.dead";

    @Bean
    CachingConnectionFactory platformRabbitConnectionFactory(@Value("${parallax.dispatch.rabbit-uri:}") String address) {
        URI uri;
        try { uri=URI.create(address); }
        catch(IllegalArgumentException ex) { throw new IllegalStateException("Invalid RabbitMQ connection configuration"); }
        if(!("amqp".equals(uri.getScheme()) || "amqps".equals(uri.getScheme())) || uri.getHost()==null || uri.getRawUserInfo()==null || !uri.getRawUserInfo().contains(":") || uri.getRawQuery()!=null || uri.getRawFragment()!=null) throw new IllegalStateException("Explicit RabbitMQ credentials and host are required");
        var factory=new CachingConnectionFactory(uri);
        factory.setPublisherConfirmType(CachingConnectionFactory.ConfirmType.CORRELATED);factory.setPublisherReturns(true);
        factory.getRabbitConnectionFactory().setAutomaticRecoveryEnabled(false);
        factory.getRabbitConnectionFactory().setConnectionTimeout(3000);factory.getRabbitConnectionFactory().setRequestedHeartbeat(30);
        if("amqps".equals(uri.getScheme())) {
            try { factory.getRabbitConnectionFactory().useSslProtocol(javax.net.ssl.SSLContext.getDefault());factory.getRabbitConnectionFactory().enableHostnameVerification(); }
            catch(java.security.NoSuchAlgorithmException ex) { throw new IllegalStateException("Default TLS context unavailable"); }
        }
        factory.setChannelCacheSize(8);
        return factory;
    }
    @Bean RabbitAdmin platformRabbitAdmin(CachingConnectionFactory factory) { return new RabbitAdmin(factory); }
    @Bean Declarables platformRabbitTopology() {
        var exchange=new DirectExchange(EXCHANGE,true,false);
        var dead=new DirectExchange(EXCHANGE+".dead",true,false);
        Queue task=dispatchQueue(TASK_QUEUE,dead.getName());
        Queue cancel=dispatchQueue(CANCEL_QUEUE,dead.getName());
        Queue dlq=QueueBuilder.durable(DEAD_QUEUE).withArgument("x-queue-type","quorum").build();
        return new Declarables(exchange,dead,task,cancel,dlq,BindingBuilder.bind(task).to(exchange).with("task"),BindingBuilder.bind(cancel).to(exchange).with("cancel"),BindingBuilder.bind(dlq).to(dead).with("dead"));
    }
    private Queue dispatchQueue(String name,String deadExchange) {
        return QueueBuilder.durable(name).withArgument("x-queue-type","quorum")
                .withArgument("x-delivery-limit",10).withArgument("x-max-length",10000)
                .withArgument("x-overflow","reject-publish").withArgument("x-dead-letter-strategy","at-least-once")
                .deadLetterExchange(deadExchange).deadLetterRoutingKey("dead").build();
    }
    @Bean RabbitTemplate platformRabbitTemplate(CachingConnectionFactory factory) { return new RabbitTemplate(factory); }
    @Bean DispatchTransport platformDispatchTransport(RabbitTemplate template) { return new RabbitDispatchTransport(template,EXCHANGE,5000); }
    @Bean PlatformOutboxDispatcher platformOutboxDispatcher(PlatformOutboxStore store,PlatformWorkerCoordinator coordinator,PlatformTaskService tasks,DispatchTransport transport,MeterRegistry metrics) {
        return new PlatformOutboxDispatcher(store,coordinator,tasks,transport,metrics);
    }
    @Bean ThreadPoolTaskScheduler platformDispatchScheduler() {
        var scheduler=new ThreadPoolTaskScheduler();scheduler.setPoolSize(2);scheduler.setThreadNamePrefix("platform-dispatch-");
        scheduler.setRemoveOnCancelPolicy(true);scheduler.setWaitForTasksToCompleteOnShutdown(true);scheduler.setAwaitTerminationSeconds(10);
        return scheduler;
    }
    @Bean PlatformDispatchLoop platformDispatchLoop(PlatformOutboxDispatcher dispatcher,PlatformWorkerCoordinator coordinator,MeterRegistry metrics) { return new PlatformDispatchLoop(dispatcher,coordinator,metrics); }
    @Bean WorkerHttpBridge platformWorkerBridge(@Value("${parallax.dispatch.worker-url:http://127.0.0.1:8000}") String url,
            @Value("${parallax.gateway.internal-token:}") String token) { return new WorkerHttpBridge(url,token); }
    @Bean SimpleMessageListenerContainer platformWorkerListener(CachingConnectionFactory factory,WorkerHttpBridge bridge,MeterRegistry metrics) {
        var listener=new SimpleMessageListenerContainer(factory);
        listener.setQueueNames(TASK_QUEUE,CANCEL_QUEUE);listener.setAcknowledgeMode(AcknowledgeMode.MANUAL);
        listener.setConcurrentConsumers(2);listener.setMaxConcurrentConsumers(4);listener.setPrefetchCount(1);
        listener.setShutdownTimeout(10000);listener.setMessageListener(new RabbitWorkerListener(bridge,metrics));
        return listener;
    }
}
