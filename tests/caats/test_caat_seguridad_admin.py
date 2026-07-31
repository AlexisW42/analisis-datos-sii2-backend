def test_caat_seguridad_admin(client, db):
    """
    CAAT de Control de Acceso basado en Roles (Seguridad).
    Audita que un usuario sin privilegios administrativos no pueda invocar
    funciones reservadas para el administrador (ej. crear otros usuarios admin o listar todo).
    """
    # 1. Registrar un usuario normal (el registro por defecto asigna el rol 'analista')
    user_normal = {"email": "analista@test.com", "password": "password123"}
    client.post("/auth/register", json=user_normal)
    
    # 2. Iniciar sesión para obtener su token
    login_resp = client.post(
        "/auth/login", 
        data={"username": user_normal["email"], "password": user_normal["password"]}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # --- PRUEBA 1: Intentar listar todos los usuarios (solo admin) ---
    resp_listar = client.get("/usuarios/admin/lista-usuarios", headers=headers)
    
    # AUDITORÍA: El control de dependencia `verificar_admin` debe bloquearlo con HTTP 403
    assert resp_listar.status_code == 403, "Fallo el control: Usuario normal pudo listar usuarios"
    assert "No tienes permisos de administrador" in resp_listar.json()["detail"]
    
    # --- PRUEBA 2: Intentar crear un usuario admin (solo admin) ---
    nuevo_usuario_hacker = {
        "email": "hacker@test.com", 
        "password": "hackerpassword", 
        "rol": "admin"
    }
    resp_crear = client.post("/usuarios/admin/create", headers=headers, json=nuevo_usuario_hacker)
    
    # AUDITORÍA: El control debe bloquear la creación de nuevos usuarios
    assert resp_crear.status_code == 403, "Fallo el control: Usuario normal pudo crear un usuario con rol admin"
    assert "No tienes permisos de administrador" in resp_crear.json()["detail"]
