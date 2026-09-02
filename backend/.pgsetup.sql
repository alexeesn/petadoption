DO $body$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pam_user') THEN
        CREATE ROLE pam_user LOGIN PASSWORD 'pam_password';
    ELSE
        ALTER ROLE pam_user WITH LOGIN PASSWORD 'pam_password';
    END IF;
END
$body$;