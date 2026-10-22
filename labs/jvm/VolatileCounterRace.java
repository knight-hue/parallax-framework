import java.util.concurrent.CountDownLatch;

public final class VolatileCounterRace {
    private static volatile int counter;
    private static final int THREADS = 8;
    private static final int INCREMENTS = 100_000;

    public static void main(String[] args) throws Exception {
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(THREADS);
        for (int i = 0; i < THREADS; i++) {
            new Thread(() -> {
                try {
                    start.await();
                    for (int j = 0; j < INCREMENTS; j++) counter++;
                } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                } finally {
                    done.countDown();
                }
            }, "counter-" + i).start();
        }
        start.countDown();
        done.await();
        int expected = THREADS * INCREMENTS;
        System.out.println("volatile counter expected=" + expected + " actual=" + counter);
        if (counter >= expected) {
            throw new AssertionError("volatile++ unexpectedly behaved atomically");
        }
        System.out.println("lost updates=" + (expected - counter)
                + " (volatile guarantees visibility, not compound-operation atomicity)");
    }
}
