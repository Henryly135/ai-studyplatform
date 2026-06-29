CREATE TABLE IF NOT EXISTS module_material_upload_sessions (
    upload_session_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_uuid VARCHAR(64) NOT NULL,
    module_id BIGINT NOT NULL,
    created_by_user_id BIGINT NOT NULL,
    title VARCHAR(200) NOT NULL,
    material_type ENUM('pdf', 'video', 'file', 'link', 'text') NOT NULL,
    sort_order INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(255) NULL,
    size_bytes BIGINT NULL,
    storage_provider VARCHAR(20) NOT NULL,
    bucket VARCHAR(100) NULL,
    object_key VARCHAR(500) NOT NULL,
    multipart_upload_id VARCHAR(255) NOT NULL,
    status ENUM('initiated', 'uploading', 'completed', 'aborted', 'failed') NOT NULL DEFAULT 'initiated',
    material_id BIGINT NULL,
    metadata_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_module_material_upload_sessions_uuid UNIQUE (session_uuid),
    CONSTRAINT fk_module_material_upload_sessions_module FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE,
    CONSTRAINT fk_module_material_upload_sessions_material FOREIGN KEY (material_id) REFERENCES module_materials (material_id) ON DELETE SET NULL
);

CREATE INDEX idx_module_material_upload_sessions_module_status
    ON module_material_upload_sessions (module_id, status);
