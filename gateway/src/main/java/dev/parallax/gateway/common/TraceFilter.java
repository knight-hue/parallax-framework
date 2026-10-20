package dev.parallax.gateway.common;

import java.io.IOException;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.util.UUID;

/**
 * 链路追踪：为每个请求分配 traceId 并写入 MDC 与响应头。
 *
 * 上游若已带 X-Trace-Id（例如来自公网边缘），沿用而不覆盖——
 * 否则跨服务的日志就串不起来了。
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TraceFilter extends OncePerRequestFilter {

    public static final String TRACE_HEADER = "X-Trace-Id";
    private static final String MDC_KEY = "traceId";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String traceId = request.getHeader(TRACE_HEADER);
        if (traceId == null || !traceId.matches("[A-Za-z0-9_-]{1,64}")) {
            traceId = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        }
        MDC.put(MDC_KEY, traceId);
        response.setHeader(TRACE_HEADER, traceId);
        try {
            chain.doFilter(request, response);
        } finally {
            // 线程池复用下不清理 MDC 会把 traceId 串到别的请求上
            MDC.remove(MDC_KEY);
        }
    }

    public static String currentTraceId() {
        return MDC.get(MDC_KEY);
    }
}
