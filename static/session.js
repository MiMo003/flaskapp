async function enviarPassword(event) {
    event.preventDefault(); // Evita recargar la página

    let passwordIngresada = document.getElementById("password").value.trim();

    try {
        let response = await fetch("/password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password: passwordIngresada })
        });

        let data = await response.json();

        if (data.valid) {
            window.location.href = data.redirect; // Redirige a /config
        } else {
            alert("Contraseña incorrecta.");
        }
    } catch (error) {
        console.error("Error:", error);
        alert("Ocurrió un error, intenta de nuevo.");
    }
}

// Verifica con el servidor si la sesión está activa
async function verificarAcceso() {
    try {
        let response = await fetch("/verificar_sesion");
        let data = await response.json();

        if (!data.activa) {
            window.location.href = "/password"; // Redirige si no hay sesión
        }
    } catch (error) {
        console.error("Error verificando sesión:", error);
        window.location.href = "/password"; // En caso de error, redirigir
    }
}

// Función para cerrar sesión correctamente
async function salir() {
    try {
        await fetch("/logout", { method: "POST" });
        window.location.href = "/password"; // Redirigir a la página de login
    } catch (error) {
        console.error("Error cerrando sesión:", error);
    }
}
