from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Sets up the raw SQL database tables for the Smart Bus System'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Setting up Smart Bus System database tables...'))
        
        sql_statements = [
            # =====================================================
            # ROUTES TABLE
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS routes (
                route_id INT AUTO_INCREMENT,
                route_name VARCHAR(100) NOT NULL,
                route_code VARCHAR(20) NOT NULL,
                description TEXT,
                color VARCHAR(7) DEFAULT '#3B82F6',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT pk_routes PRIMARY KEY (route_id),
                CONSTRAINT uk_routes_route_name UNIQUE (route_name),
                CONSTRAINT uk_routes_route_code UNIQUE (route_code)
            )
            """,

            # =====================================================
            # STOPS TABLE
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS stops (
                stop_id INT AUTO_INCREMENT,
                stop_name VARCHAR(100) NOT NULL,
                description TEXT,
                latitude DECIMAL(10, 8) NOT NULL,
                longitude DECIMAL(11, 8) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT pk_stops PRIMARY KEY (stop_id)
            )
            """,

            # =====================================================
            # ROUTE_STOPS TABLE (Junction)
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS route_stops (
                route_stop_id INT AUTO_INCREMENT,
                route_id INT NOT NULL,
                stop_id INT NOT NULL,
                sequence_number INT NOT NULL,
                distance_from_prev_meters INT DEFAULT 0,
                CONSTRAINT pk_route_stops PRIMARY KEY (route_stop_id),
                CONSTRAINT uk_route_stops UNIQUE (route_id, stop_id),
                CONSTRAINT fk_route_stops_route_id FOREIGN KEY (route_id)
                    REFERENCES routes (route_id) ON DELETE CASCADE,
                CONSTRAINT fk_route_stops_stop_id FOREIGN KEY (stop_id)
                    REFERENCES stops (stop_id) ON DELETE CASCADE
            )
            """,

            # =====================================================
            # BUSES TABLE
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS buses (
                bus_id INT AUTO_INCREMENT,
                registration_number VARCHAR(20) NOT NULL,
                capacity INT NOT NULL DEFAULT 50,
                status ENUM('active', 'inactive', 'maintenance') DEFAULT 'active',
                route_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT pk_buses PRIMARY KEY (bus_id),
                CONSTRAINT uk_buses_registration_number UNIQUE (registration_number),
                CONSTRAINT fk_buses_route_id FOREIGN KEY (route_id)
                    REFERENCES routes (route_id) ON DELETE SET NULL
            )
            """,

            # =====================================================
            # BUS_LOCATIONS TABLE
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS bus_locations (
                location_id INT AUTO_INCREMENT,
                bus_id INT NOT NULL,
                latitude DECIMAL(10, 8) NOT NULL,
                longitude DECIMAL(11, 8) NOT NULL,
                speed DECIMAL(5, 2) DEFAULT 0,
                heading DECIMAL(5, 2) DEFAULT 0,
                current_stop_sequence INT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT pk_bus_locations PRIMARY KEY (location_id),
                CONSTRAINT fk_bus_locations_bus_id FOREIGN KEY (bus_id)
                    REFERENCES buses (bus_id) ON DELETE CASCADE,
                INDEX idx_bus_locations_bus_time (bus_id, recorded_at DESC)
            )
            """,

            # =====================================================
            # DISPLAY_UNITS TABLE
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS display_units (
                display_id INT AUTO_INCREMENT,
                display_name VARCHAR(100) NOT NULL,
                stop_id INT NOT NULL,
                location VARCHAR(255),
                status ENUM('online', 'offline', 'error') DEFAULT 'offline',
                last_heartbeat TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT pk_display_units PRIMARY KEY (display_id),
                CONSTRAINT uk_display_units_stop_id UNIQUE (stop_id),
                CONSTRAINT fk_display_units_stop_id FOREIGN KEY (stop_id)
                    REFERENCES stops (stop_id) ON DELETE CASCADE
            )
            """,

            # =====================================================
            # ANNOUNCEMENTS TABLE
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS announcements (
                announcement_id INT AUTO_INCREMENT,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                message_ur TEXT,
                severity ENUM('info', 'warning', 'emergency') DEFAULT 'info',
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                created_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT pk_announcements PRIMARY KEY (announcement_id),
                CONSTRAINT fk_announcements_created_by FOREIGN KEY (created_by)
                    REFERENCES api_usermodel (id) ON DELETE SET NULL
            )
            """,

            # =====================================================
            # ANNOUNCEMENT_ROUTES TABLE (Junction)
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS announcement_routes (
                id INT AUTO_INCREMENT,
                announcement_id INT NOT NULL,
                route_id INT NOT NULL,
                CONSTRAINT pk_announcement_routes PRIMARY KEY (id),
                CONSTRAINT uk_announcement_routes UNIQUE (announcement_id, route_id),
                CONSTRAINT fk_announcement_routes_announcement FOREIGN KEY (announcement_id)
                    REFERENCES announcements (announcement_id) ON DELETE CASCADE,
                CONSTRAINT fk_announcement_routes_route FOREIGN KEY (route_id)
                    REFERENCES routes (route_id) ON DELETE CASCADE
            )
            """,

            # =====================================================
            # ADVERTISEMENTS TABLE
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS advertisements (
                ad_id INT AUTO_INCREMENT,
                title VARCHAR(100) NOT NULL,
                content_url VARCHAR(500) NOT NULL,
                media_type ENUM('image', 'youtube') NOT NULL DEFAULT 'image',
                duration_sec INT NOT NULL DEFAULT 15,
                advertiser_name VARCHAR(100) NOT NULL,
                advertiser_contact VARCHAR(100),
                metadata JSON,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT pk_advertisements PRIMARY KEY (ad_id)
            )
            """,

            # =====================================================
            # AD_SCHEDULE TABLE (Junction)
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS ad_schedule (
                schedule_id INT AUTO_INCREMENT,
                ad_id INT NOT NULL,
                display_id INT NOT NULL,
                priority INT DEFAULT 1,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT pk_ad_schedule PRIMARY KEY (schedule_id),
                CONSTRAINT fk_ad_schedule_ad_id FOREIGN KEY (ad_id)
                    REFERENCES advertisements (ad_id) ON DELETE CASCADE,
                CONSTRAINT fk_ad_schedule_display_id FOREIGN KEY (display_id)
                    REFERENCES display_units (display_id) ON DELETE CASCADE
            )
            """,

            # =====================================================
            # AUDIT_LOGS TABLE
            # =====================================================
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INT AUTO_INCREMENT,
                user_id BIGINT,
                action VARCHAR(50) NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                entity_id INT NOT NULL,
                changes JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT pk_audit_logs PRIMARY KEY (log_id),
                CONSTRAINT fk_audit_logs_user_id FOREIGN KEY (user_id)
                    REFERENCES api_usermodel (id) ON DELETE SET NULL,
                INDEX idx_audit_logs_entity (entity_type, entity_id),
                INDEX idx_audit_logs_user (user_id)
            )
            """,
        ]

        table_names = [
            'routes',
            'stops', 
            'route_stops',
            'buses',
            'bus_locations',
            'display_units',
            'announcements',
            'announcement_routes',
            'advertisements',
            'ad_schedule',
            'audit_logs',
        ]

        with connection.cursor() as cursor:
            for i, sql in enumerate(sql_statements):
                try:
                    cursor.execute(sql)
                    self.stdout.write(self.style.SUCCESS(f'Created table: {table_names[i]}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error creating {table_names[i]}: {e}'))

        self.stdout.write(self.style.SUCCESS('\nDatabase setup complete!'))
        self.stdout.write(self.style.NOTICE(
            '\nNote: Make sure you have run Django migrations first:\n'
            '  python manage.py makemigrations\n'
            '  python manage.py migrate'
        ))
