use std::{
    env,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
};

use tauri::Manager;

const BACKEND_URL: &str = "http://127.0.0.1:8765";

struct BackendState {
    child: Mutex<Option<Child>>,
}

impl Drop for BackendState {
    fn drop(&mut self) {
        if let Ok(mut child) = self.child.lock() {
            if let Some(mut process) = child.take() {
                let _ = process.kill();
            }
        }
    }
}

/// Return the local FastAPI endpoint used by the frontend.
#[tauri::command]
fn backend_url() -> String {
    BACKEND_URL.to_string()
}

fn backend_dir() -> Option<PathBuf> {
    // Return the backend directory relative to the Tauri manifest.
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|root| root.join("backend"))
}

fn start_backend_process() -> Option<Child> {
    // Start the local FastAPI subprocess unless an external backend is used.
    if env::var("PAPERREADY_BACKEND_EXTERNAL").ok().as_deref() == Some("1") {
        return None;
    }
    let python = env::var("PAPERREADY_PYTHON").unwrap_or_else(|_| "python".to_string());
    let dir = backend_dir()?;
    Command::new(python)
        .args([
            "-m",
            "uvicorn",
            "paper_ready_backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ])
        .current_dir(dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            app.manage(BackendState {
                child: Mutex::new(start_backend_process()),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_url])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
