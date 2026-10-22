import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

public final class AqsLockLab {
    public static void main(String[] args) throws Exception {
        System.out.println("== ReentrantLock / Condition / fairness ==");
        ReentrantLock lock = new ReentrantLock(true);
        lock.lock();
        try {
            lock.lock();
            System.out.println("holdCount=" + lock.getHoldCount() + " fair=" + lock.isFair());
        } finally {
            lock.unlock();
            lock.unlock();
        }

        Condition condition = lock.newCondition();
        Thread waiter = new Thread(() -> {
            lock.lock();
            try {
                boolean signalled = condition.await(2, TimeUnit.SECONDS);
                System.out.println("condition signalled=" + signalled);
            } catch (InterruptedException ex) {
                Thread.currentThread().interrupt();
            } finally {
                lock.unlock();
            }
        }, "condition-waiter");
        waiter.start();
        Thread.sleep(100);
        lock.lock();
        try { condition.signal(); } finally { lock.unlock(); }
        waiter.join(3000);
        if (waiter.isAlive()) throw new AssertionError("condition waiter did not finish");

        ExecutorService pool = Executors.newSingleThreadExecutor();
        try {
            pool.submit(() -> {
                lock.lock();
                try { Thread.sleep(400); } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                } finally { lock.unlock(); }
            });
            Thread.sleep(100);
            boolean acquired = lock.tryLock(100, TimeUnit.MILLISECONDS);
            System.out.println("tryLock while another thread holds lock=" + acquired);
            if (acquired) lock.unlock();
        } finally {
            pool.shutdownNow();
        }
    }
}
