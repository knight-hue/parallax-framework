package dev.parallax.gateway.proxy;

import java.io.InputStream;
import java.net.http.HttpHeaders;

/** 上游响应的头 + 未消费的响应体流。 */
public record UpstreamResponse(int status, HttpHeaders headers, InputStream body) {
}
