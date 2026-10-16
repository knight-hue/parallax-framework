package dev.parallax.gateway.common;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.stream.Collectors;

import dev.parallax.gateway.identity.QuotaService;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * 全局异常处理：统一为 { success:false, error }，不向客户端泄露堆栈。
 *
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Result<Void>> handleApi(ApiException ex) {
        return ResponseEntity.status(ex.getStatus()).body(Result.fail(ex.getMessage()));
    }

    /**
     * 额度用尽要带结构化字段，调用方才知道"用完了多少、上限多少、什么时候恢复"。
     * 只回一句"额度已用尽"会让人无从判断该等 1 分钟还是 1 个月。
     */
    @ExceptionHandler(QuotaService.QuotaApiException.class)
    public ResponseEntity<Map<String, Object>> handleQuota(QuotaService.QuotaApiException ex) {
        QuotaService.Decision decision = ex.getDecision();
        Map<String, Object> body = decision.asBody();
        ResponseEntity.BodyBuilder builder = ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS);
        if (decision.resetsAt() != null) {
            long seconds = Math.max(1, Duration.between(Instant.now(), decision.resetsAt()).toSeconds());
            builder = builder.header("Retry-After", Long.toString(seconds));
        }
        return builder.body(body);
    }

    /** 方法级鉴权失败必须映射为 403，否则会被兜底处理器吞成 500。 */
    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<Result<Void>> handleAccessDenied(AccessDeniedException ex) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Result.fail("无权限执行该操作"));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Result<Void>> handleValidation(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldErrors().stream()
                .map(e -> e.getField() + " " + e.getDefaultMessage())
                .collect(Collectors.joining("；"));
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(Result.fail(message.isBlank() ? "请求参数不合法" : message));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Result<Void>> handleUnreadable(HttpMessageNotReadableException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Result.fail("请求体必须为 JSON"));
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<Result<Void>> handleNotFound(NoResourceFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Result.fail("接口不存在"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Void>> handleOther(Exception ex) {
        log.error("unhandled exception", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Result.fail("服务暂时不可用，请稍后重试"));
    }
}
