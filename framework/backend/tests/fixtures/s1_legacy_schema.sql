-- Old schema only, retained exclusively for migration regression tests. No user data.
CREATE TABLE ai_scores (
	id INTEGER NOT NULL,
	session_id INTEGER NOT NULL,
	accuracy_score FLOAT NOT NULL,
	efficiency_score FLOAT NOT NULL,
	operation_quality FLOAT NOT NULL,
	total_score FLOAT NOT NULL,
	ai_comment TEXT NOT NULL,
	wrong_operations JSON NOT NULL,
	suggestions JSON NOT NULL,
	deepseek_response JSON NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(session_id) REFERENCES exercise_sessions (id)
);
CREATE TABLE device_states (
	id INTEGER NOT NULL,
	station_id INTEGER NOT NULL,
	device_type VARCHAR(20) NOT NULL,
	device_code VARCHAR(20) NOT NULL,
	state_payload JSON NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_device_state UNIQUE (station_id, device_type, device_code),
	FOREIGN KEY(station_id) REFERENCES stations (id)
);
CREATE TABLE exercise_sessions (
	id INTEGER NOT NULL,
	student_id INTEGER NOT NULL,
	exercise_id INTEGER NOT NULL,
	station_id INTEGER NOT NULL,
	start_time DATETIME NOT NULL,
	end_time DATETIME,
	total_time INTEGER,
	total_clicks INTEGER NOT NULL,
	valid_clicks INTEGER NOT NULL,
	invalid_clicks INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	completion_status VARCHAR(20),
	final_snapshot JSON,
	result_summary JSON NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(student_id) REFERENCES users (id),
	FOREIGN KEY(exercise_id) REFERENCES exercises (id),
	FOREIGN KEY(station_id) REFERENCES stations (id)
);
CREATE TABLE exercises (
	id INTEGER NOT NULL,
	teacher_id INTEGER NOT NULL,
	station_id INTEGER NOT NULL,
	title VARCHAR(200) NOT NULL,
	description TEXT,
	exercise_type VARCHAR(30) NOT NULL,
	target_routes JSON NOT NULL,
	time_limit INTEGER NOT NULL,
	difficulty VARCHAR(20) NOT NULL,
	scoring_rules JSON NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(teacher_id) REFERENCES users (id),
	FOREIGN KEY(station_id) REFERENCES stations (id)
);
CREATE TABLE feedback_snippets (
	id INTEGER NOT NULL,
	owner_id INTEGER NOT NULL,
	text VARCHAR(2000) NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(owner_id) REFERENCES users (id)
);
CREATE TABLE grade_audits (
	id INTEGER NOT NULL,
	attempt_id INTEGER NOT NULL,
	reviewer_id INTEGER NOT NULL,
	"before" JSON NOT NULL,
	"after" JSON NOT NULL,
	reason VARCHAR(1000) NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(attempt_id) REFERENCES lab_attempts (id),
	FOREIGN KEY(reviewer_id) REFERENCES users (id)
);
CREATE TABLE grade_drafts (
	id INTEGER NOT NULL,
	attempt_id INTEGER NOT NULL,
	reviewer_id INTEGER NOT NULL,
	content JSON NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (attempt_id, reviewer_id),
	FOREIGN KEY(attempt_id) REFERENCES lab_attempts (id),
	FOREIGN KEY(reviewer_id) REFERENCES users (id)
);
CREATE TABLE interlocking_tables (
	id INTEGER NOT NULL,
	station_id INTEGER NOT NULL,
	route_name VARCHAR(100) NOT NULL,
	entry_signal VARCHAR(20) NOT NULL,
	exit_signal VARCHAR(20) NOT NULL,
	route_type VARCHAR(20) NOT NULL,
	switches_required JSON NOT NULL,
	sections_required JSON NOT NULL,
	hostile_routes JSON NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(station_id) REFERENCES stations (id)
);
CREATE TABLE lab_attempts (
	id INTEGER NOT NULL,
	question_id INTEGER NOT NULL,
	student_id INTEGER NOT NULL,
	question_snapshot JSON NOT NULL,
	answers JSON NOT NULL,
	result JSON NOT NULL,
	review JSON,
	reviewer_id INTEGER,
	reviewed_at DATETIME,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(question_id) REFERENCES lab_questions (id),
	FOREIGN KEY(student_id) REFERENCES users (id),
	FOREIGN KEY(reviewer_id) REFERENCES users (id)
);
CREATE TABLE lab_questions (
	id INTEGER NOT NULL,
	"key" VARCHAR(80) NOT NULL,
	dataset_id INTEGER NOT NULL,
	topic INTEGER NOT NULL,
	sequence INTEGER NOT NULL,
	content JSON NOT NULL,
	fingerprint VARCHAR(64) NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	UNIQUE ("key"),
	FOREIGN KEY(dataset_id) REFERENCES shunting_datasets (id)
);
CREATE TABLE module_one_attempts (
	id VARCHAR(36) NOT NULL,
	owner_id INTEGER NOT NULL,
	question_id VARCHAR(60) NOT NULL,
	mode VARCHAR(20) NOT NULL,
	preview BOOLEAN NOT NULL,
	status VARCHAR(20) NOT NULL,
	version INTEGER NOT NULL,
	question_snapshot JSON NOT NULL,
	source_fingerprint VARCHAR(64) NOT NULL,
	state JSON NOT NULL,
	initial_snapshot JSON NOT NULL,
	result JSON,
	notes VARCHAR(6000) NOT NULL,
	started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	submitted_at DATETIME,
	PRIMARY KEY (id),
	FOREIGN KEY(owner_id) REFERENCES users (id)
);
CREATE TABLE module_one_events (
	id VARCHAR(36) NOT NULL,
	attempt_id VARCHAR(36) NOT NULL,
	command_id VARCHAR(36) NOT NULL,
	after_version INTEGER NOT NULL,
	command JSON NOT NULL,
	before_snapshot JSON NOT NULL,
	response JSON NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (attempt_id, command_id),
	UNIQUE (attempt_id, after_version),
	FOREIGN KEY(attempt_id) REFERENCES module_one_attempts (id)
);
CREATE TABLE operation_logs (
	id INTEGER NOT NULL,
	session_id INTEGER NOT NULL,
	timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	sequence_no INTEGER NOT NULL,
	operation_type VARCHAR(30) NOT NULL,
	target_code VARCHAR(50) NOT NULL,
	target_type VARCHAR(20) NOT NULL,
	operation_result VARCHAR(20) NOT NULL,
	request_payload JSON NOT NULL,
	state_before JSON NOT NULL,
	state_after JSON NOT NULL,
	error_message VARCHAR(200),
	time_spent_ms INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(session_id) REFERENCES exercise_sessions (id)
);
CREATE TABLE question_revisions (
	id INTEGER NOT NULL,
	question_id INTEGER NOT NULL,
	version INTEGER NOT NULL,
	content JSON NOT NULL,
	author_id INTEGER,
	note VARCHAR(500) NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (question_id, version),
	FOREIGN KEY(question_id) REFERENCES lab_questions (id),
	FOREIGN KEY(author_id) REFERENCES users (id)
);
CREATE TABLE question_workspaces (
	question_id INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	draft JSON,
	revision INTEGER NOT NULL,
	published_version INTEGER NOT NULL,
	updated_by INTEGER,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (question_id),
	FOREIGN KEY(question_id) REFERENCES lab_questions (id),
	FOREIGN KEY(updated_by) REFERENCES users (id)
);
CREATE TABLE route_states (
	id INTEGER NOT NULL,
	station_id INTEGER NOT NULL,
	route_name VARCHAR(100) NOT NULL,
	entry_signal VARCHAR(20) NOT NULL,
	exit_signal VARCHAR(20) NOT NULL,
	status VARCHAR(20) NOT NULL,
	locked_switches JSON NOT NULL,
	locked_sections JSON NOT NULL,
	opened_signal VARCHAR(20),
	metadata_payload JSON NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	cancelled_at DATETIME,
	released_at DATETIME,
	PRIMARY KEY (id),
	FOREIGN KEY(station_id) REFERENCES stations (id)
);
CREATE TABLE sections (
	id INTEGER NOT NULL,
	station_id INTEGER NOT NULL,
	section_code VARCHAR(20) NOT NULL,
	section_type VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(station_id) REFERENCES stations (id)
);
CREATE TABLE shunting_datasets (
	id INTEGER NOT NULL,
	dataset_key VARCHAR(80) NOT NULL,
	station_key VARCHAR(80) NOT NULL,
	station_name VARCHAR(100) NOT NULL,
	station_topology JSON NOT NULL,
	source JSON NOT NULL,
	content_sha256 VARCHAR(64) NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (dataset_key)
);
CREATE TABLE shunting_questions (
	id INTEGER NOT NULL,
	dataset_id INTEGER NOT NULL,
	route_id INTEGER NOT NULL,
	question_key VARCHAR(140) NOT NULL,
	question_type VARCHAR(40) NOT NULL,
	title VARCHAR(200) NOT NULL,
	prompt VARCHAR(1000) NOT NULL,
	difficulty VARCHAR(20) NOT NULL,
	answer_spec JSON NOT NULL,
	options JSON NOT NULL,
	source_snapshot JSON NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_shunting_question_route UNIQUE (dataset_id, route_id),
	CONSTRAINT uq_shunting_question_key UNIQUE (question_key),
	FOREIGN KEY(dataset_id) REFERENCES shunting_datasets (id),
	FOREIGN KEY(route_id) REFERENCES shunting_routes (id)
);
CREATE TABLE shunting_routes (
	id INTEGER NOT NULL,
	dataset_id INTEGER NOT NULL,
	route_number INTEGER NOT NULL,
	route_type VARCHAR(20) NOT NULL,
	origin_label VARCHAR(30) NOT NULL,
	route_name VARCHAR(120) NOT NULL,
	fields JSON NOT NULL,
	rich_text JSON NOT NULL,
	provenance JSON NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_shunting_source_number UNIQUE (dataset_id, route_number),
	FOREIGN KEY(dataset_id) REFERENCES shunting_datasets (id)
);
CREATE TABLE signals (
	id INTEGER NOT NULL,
	station_id INTEGER NOT NULL,
	signal_code VARCHAR(20) NOT NULL,
	signal_type VARCHAR(20) NOT NULL,
	position_x INTEGER NOT NULL,
	position_y INTEGER NOT NULL,
	direction VARCHAR(10) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(station_id) REFERENCES stations (id)
);
CREATE TABLE stations (
	id INTEGER NOT NULL,
	station_name VARCHAR(100) NOT NULL,
	station_code VARCHAR(50) NOT NULL,
	description TEXT,
	station_config JSON NOT NULL,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE switches (
	id INTEGER NOT NULL,
	station_id INTEGER NOT NULL,
	switch_code VARCHAR(20) NOT NULL,
	switch_type VARCHAR(20) NOT NULL,
	normal_position VARCHAR(10) NOT NULL,
	position_x INTEGER NOT NULL,
	position_y INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(station_id) REFERENCES stations (id)
);
CREATE TABLE users (
	id INTEGER NOT NULL,
	username VARCHAR(50) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	real_name VARCHAR(50),
	role VARCHAR(20) NOT NULL,
	student_id VARCHAR(30),
	class_name VARCHAR(50),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX ix_ai_scores_id ON ai_scores (id);
CREATE UNIQUE INDEX ix_ai_scores_session_id ON ai_scores (session_id);
CREATE INDEX ix_device_states_device_code ON device_states (device_code);
CREATE INDEX ix_device_states_device_type ON device_states (device_type);
CREATE INDEX ix_device_states_id ON device_states (id);
CREATE INDEX ix_device_states_station_id ON device_states (station_id);
CREATE INDEX ix_exercise_sessions_exercise_id ON exercise_sessions (exercise_id);
CREATE INDEX ix_exercise_sessions_id ON exercise_sessions (id);
CREATE INDEX ix_exercise_sessions_station_id ON exercise_sessions (station_id);
CREATE INDEX ix_exercise_sessions_status ON exercise_sessions (status);
CREATE INDEX ix_exercise_sessions_student_id ON exercise_sessions (student_id);
CREATE INDEX ix_exercises_id ON exercises (id);
CREATE INDEX ix_exercises_station_id ON exercises (station_id);
CREATE INDEX ix_exercises_teacher_id ON exercises (teacher_id);
CREATE INDEX ix_feedback_snippets_owner_id ON feedback_snippets (owner_id);
CREATE INDEX ix_grade_audits_attempt_id ON grade_audits (attempt_id);
CREATE INDEX ix_grade_drafts_attempt_id ON grade_drafts (attempt_id);
CREATE INDEX ix_grade_drafts_reviewer_id ON grade_drafts (reviewer_id);
CREATE INDEX ix_interlocking_tables_entry_signal ON interlocking_tables (entry_signal);
CREATE INDEX ix_interlocking_tables_exit_signal ON interlocking_tables (exit_signal);
CREATE INDEX ix_interlocking_tables_id ON interlocking_tables (id);
CREATE INDEX ix_interlocking_tables_route_name ON interlocking_tables (route_name);
CREATE INDEX ix_interlocking_tables_station_id ON interlocking_tables (station_id);
CREATE INDEX ix_lab_attempts_question_id ON lab_attempts (question_id);
CREATE INDEX ix_lab_attempts_student_id ON lab_attempts (student_id);
CREATE INDEX ix_lab_questions_topic ON lab_questions (topic);
CREATE INDEX ix_module_one_attempts_owner_id ON module_one_attempts (owner_id);
CREATE INDEX ix_module_one_attempts_question_id ON module_one_attempts (question_id);
CREATE INDEX ix_module_one_events_attempt_id ON module_one_events (attempt_id);
CREATE INDEX ix_operation_logs_id ON operation_logs (id);
CREATE INDEX ix_operation_logs_session_id ON operation_logs (session_id);
CREATE INDEX ix_question_revisions_question_id ON question_revisions (question_id);
CREATE INDEX ix_question_workspaces_status ON question_workspaces (status);
CREATE INDEX ix_route_states_entry_signal ON route_states (entry_signal);
CREATE INDEX ix_route_states_id ON route_states (id);
CREATE INDEX ix_route_states_route_name ON route_states (route_name);
CREATE INDEX ix_route_states_station_id ON route_states (station_id);
CREATE INDEX ix_route_states_status ON route_states (status);
CREATE INDEX ix_sections_id ON sections (id);
CREATE INDEX ix_sections_section_code ON sections (section_code);
CREATE INDEX ix_sections_station_id ON sections (station_id);
CREATE INDEX ix_shunting_questions_dataset_id ON shunting_questions (dataset_id);
CREATE INDEX ix_shunting_questions_route_id ON shunting_questions (route_id);
CREATE INDEX ix_shunting_routes_dataset_id ON shunting_routes (dataset_id);
CREATE INDEX ix_signals_id ON signals (id);
CREATE INDEX ix_signals_signal_code ON signals (signal_code);
CREATE INDEX ix_signals_station_id ON signals (station_id);
CREATE INDEX ix_stations_id ON stations (id);
CREATE UNIQUE INDEX ix_stations_station_code ON stations (station_code);
CREATE INDEX ix_switches_id ON switches (id);
CREATE INDEX ix_switches_station_id ON switches (station_id);
CREATE INDEX ix_switches_switch_code ON switches (switch_code);
CREATE INDEX ix_users_id ON users (id);
CREATE INDEX ix_users_role ON users (role);
CREATE UNIQUE INDEX ix_users_username ON users (username);
