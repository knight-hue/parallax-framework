package dev.parallax.labs.mysql;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/** Plain JDBC connections to the lab database; no pool, so tests control transaction boundaries. */
public final class LabConnections {

    private static final String URL = System.getenv().getOrDefault("PARALLAX_MYSQL_LAB_URL",
            "jdbc:mysql://127.0.0.1:3307/mysql_lab?connectionTimeZone=UTC"
                    + "&forceConnectionTimeZoneToSession=true&allowPublicKeyRetrieval=true&sslMode=DISABLED");
    private static final String USER = System.getenv().getOrDefault("PARALLAX_MYSQL_LAB_USER", "parallax");
    private static final String PASSWORD = System.getenv().getOrDefault("PARALLAX_MYSQL_LAB_PASSWORD", "parallax");

    private LabConnections() {
    }

    public static Connection open() throws SQLException {
        return DriverManager.getConnection(URL, USER, PASSWORD);
    }

    public static String url() {
        return URL;
    }
}
