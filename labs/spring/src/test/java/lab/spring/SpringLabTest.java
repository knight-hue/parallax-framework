package lab.spring;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;

import jakarta.annotation.PostConstruct;
import org.aopalliance.intercept.MethodInterceptor;
import org.junit.jupiter.api.Test;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.beans.factory.config.BeanPostProcessor;import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

class SpringLabTest {

    @Test
    void autoConfigurationAppliesAndUserBeanOverridesIt() {
        var runner = new ApplicationContextRunner()
                .withConfiguration(AutoConfigurations.of(GreetingAutoConfiguration.class));
        runner.run(context -> {
            assertThat(context).hasSingleBean(GreetingService.class);
            assertThat(context.getBean(GreetingService.class).greet("world")).isEqualTo("auto world");
        });
        runner.withUserConfiguration(UserConfiguration.class).run(context -> {
            assertThat(context.getBean(GreetingService.class).greet("world")).isEqualTo("user world");
        });
    }

    @Test
    void beanPostProcessorAndLifecycleOrder() {
        LifecycleBean.EVENTS.clear();
        try (var context = new AnnotationConfigApplicationContext()) {
            context.register(LifecycleBean.class, RecordingPostProcessor.class);
            context.refresh();
            assertThat(LifecycleBean.EVENTS).containsExactly(
                    "beforeInitialization", "postConstruct", "afterPropertiesSet", "afterInitialization");
        }
        assertThat(LifecycleBean.EVENTS).contains("destroy");
    }

    @Test
    void selfInvocationBypassesTheProxy() {
        List<String> calls = new ArrayList<>();
        ProxyFactory factory = new ProxyFactory(new Target());
        factory.addAdvice((MethodInterceptor) invocation -> {
            calls.add(invocation.getMethod().getName());
            return invocation.proceed();
        });
        Outer proxy = (Outer) factory.getProxy();
        assertThat(proxy.outer()).isEqualTo("inner");
        assertThat(calls).containsExactly("outer");
    }

    @Configuration
    static class UserConfiguration {
        @Bean
        GreetingService customGreeting() {
            return new DefaultGreetingService("user");
        }
    }

    static final class LifecycleBean implements InitializingBean, DisposableBean {
        static final List<String> EVENTS = new ArrayList<>();

        @PostConstruct
        void postConstruct() {
            EVENTS.add("postConstruct");
        }

        @Override
        public void afterPropertiesSet() {
            EVENTS.add("afterPropertiesSet");
        }

        @Override
        public void destroy() {
            EVENTS.add("destroy");
        }
    }

    static final class RecordingPostProcessor implements BeanPostProcessor {
        @Override
        public Object postProcessBeforeInitialization(Object bean, String beanName) {
            LifecycleBean.EVENTS.add("beforeInitialization");
            return bean;
        }

        @Override
        public Object postProcessAfterInitialization(Object bean, String beanName) {
            LifecycleBean.EVENTS.add("afterInitialization");
            return bean;
        }
    }

    interface Outer {
        String outer();
    }

    static final class Target implements Outer {
        @Override
        public String outer() {
            return inner();
        }

        String inner() {
            return "inner";
        }
    }
}
