import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public final class ThreadPoolRejectionLab {
    public static void main(String[] args) throws Exception {
        AtomicInteger accepted = new AtomicInteger();
        AtomicInteger rejected = new AtomicInteger();
        ThreadPoolExecutor pool = new ThreadPoolExecutor(
                2, 2, 0, TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(2),
                new ThreadPoolExecutor.AbortPolicy());
        try {
            for (int i = 0; i < 10; i++) {
                try {
                    pool.execute(() -> {
                        try { Thread.sleep(120); } catch (InterruptedException ex) {
                            Thread.currentThread().interrupt();
                        }
                    });
                    accepted.incrementAndGet();
                } catch (RejectedExecutionException ex) {
                    rejected.incrementAndGet();
                }
            }
            System.out.println("accepted=" + accepted.get() + " rejected=" + rejected.get()
                    + " (2 running + queue cap 2)");
            if (accepted.get() != 4 || rejected.get() != 6) {
                throw new AssertionError("unexpected rejection count");
            }
        } finally {
            pool.shutdown();
            pool.awaitTermination(2, TimeUnit.SECONDS);
        }
    }
}
