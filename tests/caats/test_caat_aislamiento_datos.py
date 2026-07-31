def test_caat_aislamiento_datos(client, db):
    """
    CAAT de Control de Aislamiento de Datos.
    Audita que un usuario no pueda acceder a los datasets que pertenecen a otro usuario.
    """
    # 1. Registrar dos usuarios diferentes
    user_a_data = {"email": "usera@test.com", "password": "passwordA"}
    user_b_data = {"email": "userb@test.com", "password": "passwordB"}
    
    client.post("/auth/register", json=user_a_data)
    client.post("/auth/register", json=user_b_data)
    
    # 2. Login como Usuario A
    login_resp_a = client.post(
        "/auth/login", 
        data={"username": user_a_data["email"], "password": user_a_data["password"]}
    )
    token_a = login_resp_a.json()["access_token"]
    
    # 3. Usuario A sube un archivo (Dataset simulado)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # Simulamos subir un archivo CSV
    with open("test_dataset.csv", "w") as f:
        f.write("col1,col2\n1,2")
        
    with open("test_dataset.csv", "rb") as f:
        upload_resp = client.post(
            "/carga/cargar",
            headers=headers_a,
            data={"nombre": "Dataset Privado de A", "descripcion": "Confidencial"},
            files={"file": ("test_dataset.csv", f, "text/csv")}
        )
    
    assert upload_resp.status_code == 200, "Error en carga inicial"
    dataset_id = upload_resp.json()["dataset_id"]
    
    # 4. Login como Usuario B
    login_resp_b = client.post(
        "/auth/login", 
        data={"username": user_b_data["email"], "password": user_b_data["password"]}
    )
    token_b = login_resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # 5. Usuario B intenta obtener el contenido del dataset del Usuario A
    intentar_ver_resp = client.get(f"/carga/datasets/{dataset_id}/contenido", headers=headers_b)
    
    # AUDITORÍA: El sistema debe rechazar a Usuario B con 404 (No encontrado por aislamiento)
    assert intentar_ver_resp.status_code == 404, "Fallo el control: Usuario B pudo ver el dataset de A"
    assert "Dataset no encontrado" in intentar_ver_resp.json()["detail"]
    
    # 6. Usuario B intenta eliminar el dataset del Usuario A
    intentar_eliminar_resp = client.delete(f"/carga/datasets/{dataset_id}", headers=headers_b)
    
    # AUDITORÍA: El sistema debe rechazar la eliminación
    assert intentar_eliminar_resp.status_code == 404, "Fallo el control: Usuario B pudo eliminar el dataset de A"
