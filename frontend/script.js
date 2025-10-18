// ============================================================================
// UPLOAD HANDLER - Drag and Drop + Click
// ============================================================================

const uploadArea = document.getElementById("uploadArea");
const pdfFile = document.getElementById("pdfFile");
const fileName = document.getElementById("fileName");
const uploadForm = document.getElementById("uploadForm");
const submitBtn = document.getElementById("submitBtn");
const resetBtn = document.getElementById("resetBtn");

// Inicialmente desabilita o botão de converter
submitBtn.disabled = true;

function setSubmitEnabled(enabled) {
    submitBtn.disabled = !enabled;
}

// Drag and Drop
uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadArea.classList.add("dragover");
});

uploadArea.addEventListener("dragleave", () => {
    uploadArea.classList.remove("dragover");
});

uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadArea.classList.remove("dragover");

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        const pdfFiles = Array.from(files).filter(
            (file) =>
                file.type === "application/pdf" || file.name.endsWith(".pdf"),
        );

        if (pdfFiles.length > 0) {
            // Criar DataTransfer para atualizar o input
            const dataTransfer = new DataTransfer();
            pdfFiles.forEach((file) => dataTransfer.items.add(file));
            pdfFile.files = dataTransfer.files;
            updateFileNames(pdfFiles);
        } else {
            showError("Por favor, selecione apenas arquivos PDF válidos.");
        }
    }
});

// Click to select
uploadArea.addEventListener("click", () => {
    pdfFile.click();
});

pdfFile.addEventListener("change", (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
        updateFileNames(files);
    } else {
        setSubmitEnabled(false);
    }
});

function updateFileNames(files) {
    if (files.length === 0) {
        fileName.textContent = "";
        fileName.style.display = "none";
        setSubmitEnabled(false);
        return;
    }

    if (files.length === 1) {
        fileName.textContent = `Arquivo selecionado: ${files[0].name}`;
    } else {
        fileName.textContent = `${files.length} arquivos selecionados: ${files
            .map((f) => f.name)
            .join(", ")}`;
    }

    fileName.style.display = "block";
    resetBtn.style.display = "inline-block";
    setSubmitEnabled(true); // Habilita o botão quando arquivo(s) é/são selecionado(s)
}

// ============================================================================
// FORM SUBMISSION
// ============================================================================

uploadForm.addEventListener("submit", async function (e) {
    e.preventDefault();

    const files = pdfFile.files;

    if (!files || files.length === 0) {
        showError("Por favor, selecione pelo menos um arquivo PDF.");
        return;
    }

    // Validar todos os arquivos
    const maxSize = 500 * 1024 * 1024; // 500MB
    for (let file of files) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showError(`Arquivo "${file.name}" não é um PDF válido.`);
            return;
        }

        if (file.size > maxSize) {
            showError(
                `Arquivo "${file.name}" é muito grande. Máximo: 500MB. Seu arquivo: ${(
                    file.size /
                    1024 /
                    1024
                ).toFixed(2)}MB`,
            );
            return;
        }
    }

    const formData = new FormData();
    for (let file of files) {
        formData.append("files", file);
    }

    showLoading(true);
    hideError();
    hideResult();

    try {
        const response = await fetch("/api/upload-multiple/", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            const errorMsg = error.detail || "Falha ao processar PDFs.";
            showError(`Erro: ${errorMsg}`);
            showLoading(false);
            return;
        }

        const data = await response.json();
        const zipFile = data.zip_file;

        showLoading(false);
        showResult(zipFile);
        pdfFile.value = "";
        fileName.textContent = "";
        fileName.style.display = "none";
    } catch (err) {
        showError("Erro de conexão com o servidor.");
        console.error("Erro:", err);
        showLoading(false);
    }
});

// ============================================================================
// UI HELPERS
// ============================================================================

function showLoading(show) {
    const loading = document.getElementById("loading");
    if (loading) {
        loading.classList.toggle("hidden", !show);
    }
}

function showResult(zipFile) {
    const result = document.getElementById("result");
    const resultMessage = document.getElementById("resultMessage");
    const downloadLink = document.getElementById("downloadLink");

    if (result && resultMessage && downloadLink) {
        resultMessage.innerHTML = `
            <p><strong>✅ Conversão concluída com sucesso!</strong></p>
            <p>Arquivo ZIP consolidado: <code>${zipFile}</code></p>
            <p>Contém: Markdowns + Imagens em pasta única</p>
        `;

        downloadLink.href = `/api/download-zip/${zipFile}`;
        downloadLink.download = zipFile;
        downloadLink.textContent = "📦 Baixar ZIP Consolidado";

        result.classList.remove("hidden");
        submitBtn.style.display = "none";
        resetBtn.style.display = "inline-block";
    }
}

function hideResult() {
    const result = document.getElementById("result");
    if (result) {
        result.classList.add("hidden");
    }
    submitBtn.style.display = "inline-block";
}

function showError(message) {
    const errorDiv = document.getElementById("error");
    const errorMessage = document.getElementById("errorMessage");

    if (errorDiv && errorMessage) {
        errorMessage.textContent = message;
        errorDiv.classList.remove("hidden");
    }
}

function hideError() {
    const errorDiv = document.getElementById("error");
    if (errorDiv) {
        errorDiv.classList.add("hidden");
    }
}

// ============================================================================
// EVENT LISTENERS
// ============================================================================

document.getElementById("resetBtn")?.addEventListener("click", function () {
    hideResult();
    uploadForm.reset();
    fileName.textContent = "";
    fileName.style.display = "none";
    resetBtn.style.display = "none";
    submitBtn.style.display = "inline-block";
    setSubmitEnabled(false); // Desabilita ao resetar
});

document.getElementById("closeErrorBtn")?.addEventListener("click", hideError);

document
    .getElementById("closeResultBtn")
    ?.addEventListener("click", function () {
        hideResult();
    });
