package lab.spring;

public class DefaultGreetingService implements GreetingService {
    private final String prefix;

    public DefaultGreetingService(String prefix) {
        this.prefix = prefix;
    }

    @Override
    public String greet(String name) {
        return prefix + " " + name;
    }
}
