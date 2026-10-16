package dev.parallax.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * Parallax 薄网关入口。
 *
 * 显式排除 `UserDetailsServiceAutoConfiguration`：不排的话 Spring Security 会建一个
 * 内存用户并把随机密码打进启动日志。我们是纯令牌鉴权，不存在表单登录用户，
 * 那个默认用户只会让日志里多出一行看起来像"有人开了后门"的东西。
 */
@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
@ConfigurationPropertiesScan
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }
}
