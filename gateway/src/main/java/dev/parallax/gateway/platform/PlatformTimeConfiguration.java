package dev.parallax.gateway.platform;

import java.time.Clock;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;

@Configuration
public class PlatformTimeConfiguration {
    @Bean
    @ConditionalOnMissingBean(Clock.class)
    Clock platformClock() { return Clock.systemUTC(); }
}
