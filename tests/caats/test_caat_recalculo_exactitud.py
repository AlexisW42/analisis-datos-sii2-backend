def test_caat_recalculo_exactitud(client, db):
    """
    CAAT de Recálculo y Exactitud.
    Audita que el sistema (motor de perfilado) realice los conteos y cálculos matemáticos
    y lógicos exactamente como se espera para un set de datos controlados.
    """
    import os
    
    # 1. Crear un usuario de prueba para la sesión
    user_data = {"email": "auditor_recalculo@test.com", "password": "securepassword"}
    client.post("/auth/register", json=user_data)
    
    login_resp = client.post(
        "/auth/login", 
        data={"username": user_data["email"], "password": user_data["password"]}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # --- PRUEBA 1: Subir dataset conocido ---
    # Creamos un CSV controlado con 3 filas de datos y 2 columnas
    contenido_csv = "id,valor\n1,10.5\n2,20.0\n3,30.5"
    with open("auditoria_datos.csv", "w") as f:
        f.write(contenido_csv)
        
    with open("auditoria_datos.csv", "rb") as f:
        resp_upload = client.post(
            "/carga/cargar",
            headers=headers,
            data={"nombre": "Datos Auditoría"},
            files={"file": ("auditoria_datos.csv", f, "text/csv")}
        )
        
    dataset_id = resp_upload.json()["dataset_id"]
    
    # --- PRUEBA 2: Invocar Perfilado y auditar cálculos ---
    resp_perfilado = client.get(f"/perfilado/datasets/{dataset_id}", headers=headers)
    
    assert resp_perfilado.status_code == 200, "Falló la generación del perfilado"
    data = resp_perfilado.json()
    
    # AUDITORÍA DE RECÁLCULO:
    # Como auditores, sabemos matemáticamente que el dataset tiene 3 filas y 2 columnas.
    # Verificamos que el sistema calculó esto sin pérdida de datos.
    assert data["resumen"]["registros"] == 3, f"Fallo el control de exactitud: El sistema contó {data['resumen']['registros']} filas, se esperaban 3"
    assert data["resumen"]["variables"] == 2, f"Fallo el control de exactitud: El sistema contó {data['resumen']['variables']} columnas, se esperaban 2"
    
    # Limpieza
    if os.path.exists("auditoria_datos.csv"):
        os.remove("auditoria_datos.csv")
