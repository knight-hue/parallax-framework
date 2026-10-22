public final class SafePublicationLab {
    private static final class Holder {
        final int value;
        Holder(int value) { this.value = value; }
    }

    private static volatile Holder holder;

    public static void main(String[] args) throws Exception {
        Thread reader = new Thread(() -> {
            while (holder == null) Thread.onSpinWait();
            if (holder.value != 42) throw new AssertionError("unsafe publication");
            System.out.println("reader observed fully constructed value=" + holder.value);
        }, "reader");
        reader.start();
        Thread.sleep(100);
        holder = new Holder(42);
        reader.join(2000);
        if (reader.isAlive()) throw new AssertionError("reader did not observe publication");
        System.out.println("safe publication via volatile reference + final field passed");
    }
}
