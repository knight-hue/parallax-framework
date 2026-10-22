import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;

public final class ClassLoaderLab {
    public static void main(String[] args) throws Exception {
        Path sourceDir = Files.createTempDirectory("classloader-source");
        Path classes = Files.createTempDirectory("classloader-classes");
        Path source = sourceDir.resolve("Sample.java");
        Files.writeString(source, "public class Sample { public String value() { return \"v1\"; } }");
        try {
            JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
            if (compiler == null) throw new IllegalStateException("JDK compiler is required");
            int result = compiler.run(null, null, null, "-d", classes.toString(), source.toString());
            if (result != 0) throw new IllegalStateException("Sample.java compilation failed");

            URL url = classes.toUri().toURL();
            try (URLClassLoader first = new URLClassLoader(new URL[]{url}, null);
                 URLClassLoader second = new URLClassLoader(new URL[]{url}, null)) {
                Class<?> a = first.loadClass("Sample");
                Class<?> b = second.loadClass("Sample");
                System.out.println("same class object=" + (a == b));
                System.out.println("first loader=" + a.getClassLoader());
                System.out.println("second loader=" + b.getClassLoader());
                System.out.println("system loader parent=" + ClassLoader.getSystemClassLoader().getParent());
                if (a == b) throw new AssertionError("different loaders must define different classes");
                Object instance = a.getDeclaredConstructor().newInstance();
                System.out.println("reflective value=" + a.getMethod("value").invoke(instance));
            }
        } finally {
            delete(classes);
            delete(sourceDir);
        }
    }

    private static void delete(Path root) throws Exception {
        try (var paths = Files.walk(root)) {
            paths.sorted(Comparator.reverseOrder()).forEach(path -> {
                try { Files.deleteIfExists(path); } catch (Exception ignored) { }
            });
        }
    }
}
