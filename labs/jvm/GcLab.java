import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;

public final class GcLab {
    public static void main(String[] args) throws Exception {
        System.out.println("== GC observation ==");
        for (GarbageCollectorMXBean bean : ManagementFactory.getGarbageCollectorMXBeans()) {
            System.out.println("collector=" + bean.getName() + " count=" + bean.getCollectionCount()
                    + " timeMs=" + bean.getCollectionTime());
        }
        byte[] survivor = null;
        for (int i = 0; i < 400; i++) {
            survivor = new byte[512 * 1024];
            if (i % 4 == 0) survivor = null;
            if (i % 50 == 0) {
                Runtime runtime = Runtime.getRuntime();
                System.out.println("iteration=" + i + " usedMb="
                        + ((runtime.totalMemory() - runtime.freeMemory()) / (1024 * 1024))
                        + " totalMb=" + (runtime.totalMemory() / (1024 * 1024)));
            }
        }
        System.out.println("survivorLength=" + (survivor == null ? 0 : survivor.length));
        System.out.println("re-run with -Xlog:gc* to inspect young/mixed/full collections");
    }
}
