public final class JmmVisibilityLab {
    private static boolean plainStop;
    private static volatile boolean volatileStop;

    public static void main(String[] args) throws Exception {
        System.out.println("== JMM visibility ==");
        plainStop = false;
        Thread plain = new Thread(() -> {
            while (!plainStop) Thread.onSpinWait();
        }, "plain-reader");
        plain.setDaemon(true);
        plain.start();
        Thread.sleep(200);
        plainStop = true;
        plain.join(1000);
        System.out.println("plain flag stopped=" + !plain.isAlive()
                + " (a non-volatile read is not guaranteed to observe the write)");

        volatileStop = false;
        Thread volatileReader = new Thread(() -> {
            while (!volatileStop) Thread.onSpinWait();
        }, "volatile-reader");
        volatileReader.start();
        Thread.sleep(200);
        volatileStop = true;
        volatileReader.join(2000);
        if (volatileReader.isAlive()) throw new AssertionError("volatile stop was not observed");
        System.out.println("volatile flag stopped=true (happens-before is enforced)");
    }
}
