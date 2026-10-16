package dev.parallax.gateway.proxy;

/**
 * 网关与编排服务之间的自定义请求头。
 *
 * 集中定义而不是各处写字符串字面量：这个头的名字在两端都要用，
 * 一边改了另一边没改会导致"回调里没有归属人"这种**静默**失效——
 * 用量照样记，只是记到了别人账上或记不上。
 */
public final class CredentialHeaders {

    /** 调用方身份（API Key 对应的凭据 id）。上游需在完成回调里原样回报。 */
    public static final String CREDENTIAL_ID = "X-Parallax-Credential-Id";

    /** 网关为本请求分配的 traceId。上游需写进日志与其 run meta。 */
    public static final String TRACE_ID = "X-Trace-Id";

    private CredentialHeaders() {
    }
}
