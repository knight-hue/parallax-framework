# syntax=docker/dockerfile:1

FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
# 先只拷 pom 预热依赖层：只要 pom 没变，改 Java 代码就不会重新下载依赖
COPY pom.xml ./
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q package -DskipTests

FROM eclipse-temurin:21-jre-alpine AS runner
WORKDIR /app
RUN addgroup -S parallax && adduser -S parallax -G parallax
COPY --from=build --chown=parallax:parallax /build/target/parallax-gateway-*.jar app.jar

USER parallax
EXPOSE 8080

# JVM 在容器里默认按宿主机内存猜堆大小，会被 OOM Kill；显式给上限。
ENV JAVA_OPTS="-XX:MaxRAMPercentage=70 -XX:+UseSerialGC"

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/actuator/health/liveness || exit 1

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar app.jar"]
