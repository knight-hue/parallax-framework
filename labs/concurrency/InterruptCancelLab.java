import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public final class InterruptCancelLab {
    public static void main(String[] args) throws Exception {
        ExecutorService pool = Executors.newSingleThreadExecutor();
        AtomicBoolean interrupted = new AtomicBoolean();
        CountDownLatch started = new CountDownLatch(1);
        try {
            Future<?> future = pool.submit(() -> {
                started.countDown();
                try {
                    while (true) Thread.sleep(50);
                } catch (InterruptedException ex) {
                    interrupted.set(true);
                }
            });
            if (!started.await(2, TimeUnit.SECONDS)) throw new AssertionError("task did not start");
            Thread.sleep(100);
            boolean canceled = future.cancel(true);
            System.out.println("cancel(true)=" + canceled + " interruptedObserved="
                    + interrupted.get());
            if (!canceled || !interrupted.get()) {
                throw new AssertionError("interrupt was not propagated to the task");
            }
        } finally {
            pool.shutdownNow();
        }
    }
}
