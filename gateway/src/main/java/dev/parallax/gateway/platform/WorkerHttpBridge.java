package dev.parallax.gateway.platform;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import dev.parallax.gateway.task.WorkerProtocol;

/** Fixed operator-configured worker endpoint; never accepts a URL or path from the message. */
public final class WorkerHttpBridge {
    public enum Delivery { ACK, RETRY, DEAD_LETTER }
    private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).followRedirects(HttpClient.Redirect.NEVER).build();
    private final URI execute;
    private final URI cancel;
    private final String token;
    public WorkerHttpBridge(String base,String token) {
        URI uri=URI.create(base);
        if(!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme())) || uri.getHost()==null || uri.getRawUserInfo()!=null || uri.getRawQuery()!=null || uri.getRawFragment()!=null || token==null || token.isBlank()) throw new IllegalArgumentException("Explicit worker endpoint and internal token are required");
        String root=base.replaceAll("/+$","");this.execute=URI.create(root+"/api/v1/platform-worker/execute");this.cancel=URI.create(root+"/api/v1/platform-worker/cancel");this.token=token;
    }
    public Delivery deliver(String kind,String payload) throws InterruptedException {
        dev.parallax.gateway.task.WorkerTask task;
        try { task=WorkerProtocol.readTask(payload); }
        catch(java.io.IOException | IllegalArgumentException ex) { return Delivery.DEAD_LETTER; }
        try {
            if(kind.equals("DISPATCH")) {
                if(!task.deadline().isAfter(Instant.now())) return Delivery.ACK;
            } else if(!kind.equals("CANCEL")) return Delivery.DEAD_LETTER;
            URI target=kind.equals("DISPATCH")?execute:cancel;
            var request=HttpRequest.newBuilder(target).timeout(Duration.ofSeconds(5))
                    .header("Content-Type","application/json").header("X-Internal-Token",token)
                    .POST(HttpRequest.BodyPublishers.ofString(payload)).build();
            int status=client.send(request,HttpResponse.BodyHandlers.discarding()).statusCode();
            if((status>=200 && status<300) || status==409 || status==410) return Delivery.ACK;
            if(status==429 || status>=500) return Delivery.RETRY;
            return Delivery.DEAD_LETTER;
        } catch(java.io.IOException ex) { return Delivery.RETRY; }
        catch(IllegalArgumentException ex) { return Delivery.DEAD_LETTER; }
    }
}
