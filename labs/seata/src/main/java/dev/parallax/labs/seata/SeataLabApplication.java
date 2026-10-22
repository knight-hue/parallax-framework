package dev.parallax.labs.seata;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Seata AT/TCC lab application.
 *
 * <p>Runs against a real Seata server (file registry) and a real MySQL 8.x database.
 */
@SpringBootApplication
public class SeataLabApplication {

    public static void main(String[] args) {
        SpringApplication.run(SeataLabApplication.class, args);
    }
}
