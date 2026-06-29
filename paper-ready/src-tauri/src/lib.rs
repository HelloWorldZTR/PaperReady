use std::{
    env,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
};

use tauri::{AppHandle, Manager, State};

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

/// Restart the managed backend subprocess when Tauri owns it.
#[tauri::command]
fn restart_backend(state: State<'_, BackendState>) -> bool {
    if let Ok(mut child) = state.child.lock() {
        if let Some(mut process) = child.take() {
            let _ = process.kill();
        }
        *child = start_backend_process();
        return child.is_some();
    }
    false
}

/// Open the WebView developer tools for diagnostics.
#[tauri::command]
fn open_devtools(app: AppHandle) {
    if let Some(webview) = app.get_webview_window("main") {
        webview.open_devtools();
    }
}

fn backend_dir() -> Option<PathBuf> {
    // Return the backend directory relative to the Tauri manifest.
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|root| root.join("backend"))
}

fn sidecar_candidates() -> Vec<PathBuf> {
    // Prefer a PyInstaller backend sidecar when it exists in dev or bundled paths.
    let binary_name = if cfg!(windows) {
        "paperready-backend.exe"
    } else {
        "paperready-backend"
    };
    let mut candidates = Vec::new();
    if let Some(root) = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent() {
        candidates.push(root.join("src-tauri").join("binaries").join(binary_name));
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join(binary_name));
            candidates.push(dir.join("../Resources").join(binary_name));
            candidates.push(dir.join("../Resources/binaries").join(binary_name));
        }
    }
    candidates
}

fn spawn_uvicorn_with_python(command: &mut Command, backend: &Path) -> Option<Child> {
    // Start uvicorn using an already-configured Python command.
    let mut args = vec![
        "-m",
        "uvicorn",
        "paper_ready_backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8765",
    ];
    if cfg!(debug_assertions) {
        args.push("--reload");
    }
    command
        .args(args)
        .current_dir(backend)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

fn start_backend_process() -> Option<Child> {
    // Start the local FastAPI subprocess unless an external backend is used.
    if env::var("PAPERREADY_BACKEND_EXTERNAL").ok().as_deref() == Some("1") {
        return None;
    }
    for candidate in sidecar_candidates() {
        if candidate.exists() {
            return Command::new(candidate)
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .ok();
        }
    }
    let dir = backend_dir()?;
    if let Ok(python) = env::var("PAPERREADY_PYTHON") {
        let mut command = Command::new(python);
        return spawn_uvicorn_with_python(&mut command, &dir);
    }
    let mut command = Command::new("conda");
    command.args(["run", "-n", "generic", "python"]);
    spawn_uvicorn_with_python(&mut command, &dir)
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
        .invoke_handler(tauri::generate_handler![
            backend_url,
            open_devtools,
            restart_backend
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
