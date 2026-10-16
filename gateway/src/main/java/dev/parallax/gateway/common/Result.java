package dev.parallax.gateway.common;

/** 统一返回体。字段与 Python 侧的 `{ "detail": ... }` 不同是刻意的：
 *  网关自己的错误（鉴权、限流、熔断）与上游的业务错误必须可区分，
 *  否则前端无法判断"该重试"还是"该改参数"。 */
public record Result<T>(boolean success, T data, String error) {

    public static <T> Result<T> ok(T data) {
        return new Result<>(true, data, null);
    }

    public static <T> Result<T> fail(String error) {
        return new Result<>(false, null, error);
    }
}
