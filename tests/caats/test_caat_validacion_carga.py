def test_caat_validacion_carga(client, db):
    """
    CAAT de Validación e Integridad en la Carga de Archivos.
    Audita que el sistema impida la inyección de archivos peligrosos, vacíos o mal estructurados.
    """
    # 1. Crear un usuario de prueba para la sesión
    user_data = {"email": "validador@test.com", "password": "securepassword"}
    client.post("/auth/register", json=user_data)
    
    login_resp = client.post(
        "/auth/login", 
        data={"username": user_data["email"], "password": user_data["password"]}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # --- PRUEBA 1: Archivo con extensión no permitida (simulando inyección de binario .exe) ---
    with open("payload_malicioso.exe", "w") as f:
        f.write("archivo ejecutable simulado")
        
    with open("payload_malicioso.exe", "rb") as f:
        resp_inyeccion = client.post(
            "/carga/cargar",
            headers=headers,
            data={"nombre": "Archivo Peligroso"},
            files={"file": ("payload_malicioso.exe", f, "application/x-msdownload")}
        )
        
    # AUDITORÍA: El control preventivo (ValidadorArchivo) debe bloquear formatos no permitidos
    assert resp_inyeccion.status_code == 400, "Fallo el control: El sistema aceptó un archivo .exe"
    assert "Formato no válido" in resp_inyeccion.json()["detail"]
    
    # --- PRUEBA 2: Archivo CSV vacío ---
    with open("vacio.csv", "w") as f:
        pass
        
    with open("vacio.csv", "rb") as f:
        resp_vacio = client.post(
            "/carga/cargar",
            headers=headers,
            data={"nombre": "Archivo Vacío"},
            files={"file": ("vacio.csv", f, "text/csv")}
        )
        
    # AUDITORÍA: El control debe bloquear archivos vacíos
    assert resp_vacio.status_code == 400, "Fallo el control: El sistema aceptó un archivo sin contenido"
    assert "vacío" in resp_inyeccion.json()["detail"].lower() or "vacío" in resp_vacio.json()["detail"].lower()
    
    # --- PRUEBA 3: Archivo CSV mal estructurado (sin columnas suficientes) ---
    with open("mal_estructurado.csv", "w") as f:
        f.write("columna_unica\ndato\ndato")
        
    with open("mal_estructurado.csv", "rb") as f:
        resp_estructura = client.post(
            "/carga/cargar",
            headers=headers,
            data={"nombre": "Archivo Roto"},
            files={"file": ("mal_estructurado.csv", f, "text/csv")}
        )
        
    # AUDITORÍA: El control debe detectar un dataset que no es tabla válida
    assert resp_estructura.status_code == 400, "Fallo el control: El sistema aceptó un CSV sin formato de tabla"
    assert "estructura" in resp_estructura.json()["detail"].lower()
