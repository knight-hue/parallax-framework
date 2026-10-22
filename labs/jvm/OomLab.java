import java.util.ArrayList;
import java.util.List;

public final class OomLab {
    public static void main(String[] args) {
        System.out.println("== controlled heap OOM (run with -Xmx32m) ==");
        List<byte[]> retained = new ArrayList<>();
        try {
            for (int i = 0; i < 10_000; i++) {
                retained.add(new byte[1024 * 1024]);
                if (i % 8 == 0) System.out.println("allocatedMb=" + (i + 1));
            }
            throw new AssertionError("expected an OutOfMemoryError");
        } catch (OutOfMemoryError error) {
            System.out.println("caught=" + error.getClass().getName() + " retained=" + retained.size());
            retained.clear();
            System.out.println("released references; process can continue");
        }
    }
}
