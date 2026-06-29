CREATE TABLE IF NOT EXISTS module_prerequisites (
    module_prerequisite_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    module_id BIGINT NOT NULL,
    prerequisite_module_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_prerequisites_module_id UNIQUE (module_id),
    CONSTRAINT uq_module_prerequisites_pair UNIQUE (prerequisite_module_id, module_id),
    CONSTRAINT fk_module_prerequisites_module FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE,
    CONSTRAINT fk_module_prerequisites_prerequisite FOREIGN KEY (prerequisite_module_id) REFERENCES modules (module_id) ON DELETE CASCADE
);
