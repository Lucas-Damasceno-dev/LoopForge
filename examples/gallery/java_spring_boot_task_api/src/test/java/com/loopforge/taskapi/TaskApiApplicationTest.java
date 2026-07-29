package com.loopforge.taskapi;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class TaskApiApplicationTest {

    @Test
    public void testAddTaskAndJwtValidation() {
        TaskApiApplication app = new TaskApiApplication();
        app.addTask(new TaskApiApplication.Task("T-1", "Completar projeto LoopForge", false));

        assertEquals(1, app.getTasks().size());
        assertTrue(app.validateJwtToken("Bearer valid_jwt_token_sample"));
        assertFalse(app.validateJwtToken("invalid_token"));
    }
}
