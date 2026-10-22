import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public final class BackpressureLab {
    public static void main(String[] args) throws Exception {
        AtomicInteger active = new AtomicInteger();
        AtomicInteger peak = new AtomicInteger();
        AtomicInteger completed = new AtomicInteger();
        CountDownLatch done = new CountDownLatch(20);
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
                3, 3, 0, TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(3),
                new ThreadPoolExecutor.CallerRunsPolicy());
        try (pool) {
            for (int i = 0; i < 20; i++) {
                pool.execute(() -> {
                    int now = active.incrementAndGet();
                    peak.accumulateAndGet(now, Math::max);
                    try { Thread.sleep(20); } catch (InterruptedException ex) {
                        Thread.currentThread().interrupt();
                    } finally {
                        active.decrementAndGet();
                        completed.incrementAndGet();
                        done.countDown();
                    }
                });
            }
            if (!done.await(5, TimeUnit.SECONDS)) throw new AssertionError("tasks did not finish");
            System.out.println("completed=" + completed.get() + " peakActive=" + peak.get()
                    + " queue=" + pool.getQueue().size());
            System.out.println("CallerRunsPolicy applies backpressure by running work on the submitting thread");
        }
    }
}
