package dev.parallax.gateway.task;

import java.util.Set;

/** Platform lifecycle; retry ownership remains with the coordinator, never the worker. */
public enum TaskState {
    QUEUED, DISPATCHED, RUNNING, CANCEL_REQUESTED, SUCCEEDED, FAILED, CANCELED;

    public boolean terminal() {
        return this == SUCCEEDED || this == FAILED || this == CANCELED;
    }

    public boolean canTransitionTo(TaskState next) {
        if (next == null) return false;
        if (this == next) return true;
        return switch (this) {
            case QUEUED -> Set.of(DISPATCHED, CANCELED).contains(next);
            case DISPATCHED -> Set.of(RUNNING, QUEUED, CANCEL_REQUESTED, FAILED).contains(next);
            case RUNNING -> Set.of(QUEUED, CANCEL_REQUESTED, SUCCEEDED, FAILED).contains(next);
            // A result racing cancellation can finish before the worker acknowledges cancel.
            case CANCEL_REQUESTED -> Set.of(SUCCEEDED, FAILED, CANCELED).contains(next);
            case SUCCEEDED, FAILED, CANCELED -> false;
        };
    }

    public TaskState transitionTo(TaskState next) {
        if (!canTransitionTo(next)) {
            throw new IllegalStateException("Invalid task transition: " + this + " -> " + next);
        }
        return next;
    }
}
