const fileInput = document.getElementById("fileInput");
const uploadButton = document.getElementById("uploadButton");
const uploadStatus = document.getElementById("uploadStatus");
const askButton = document.getElementById("askButton");
const questionInput = document.getElementById("questionInput");
const answerArea = document.getElementById("answerArea");
const answerText = document.getElementById("answerText");
const sourcesArea = document.getElementById("sourcesArea");
const sourcesList = document.getElementById("sourcesList");
const resetButton = document.getElementById("resetButton");
const statusButton = document.getElementById("statusButton");

function setLoading(button, isLoading, textWhenDone) {
    if (isLoading) {
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.textContent = "Working...";
    } else {
        button.disabled = false;
        button.textContent = textWhenDone || button.dataset.originalText;
    }
}

async function refreshStatus() {
    try {
        const response = await fetch("/status");
        const data = await response.json();

        if (!data.success) {
            uploadStatus.textContent = "Status check failed.";
            return;
        }

        const fileText = data.uploaded_files.length
            ? `${data.uploaded_files.length} file(s)`
            : "no files";

        const databaseText = data.database_exists
            ? `${data.chunk_count} chunk(s) indexed`
            : "database not created yet";

        uploadStatus.textContent = `${fileText}; ${databaseText}.`;
    } catch (error) {
        uploadStatus.textContent = "Status check failed. Is the backend running?";
    }
}

uploadButton.addEventListener("click", async () => {
    const files = fileInput.files;

    if (!files.length) {
        uploadStatus.textContent = "Please choose at least one file.";
        return;
    }

    const formData = new FormData();

    for (const file of files) {
        formData.append("files", file);
    }

    uploadStatus.textContent = "Uploading and indexing documents...";
    setLoading(uploadButton, true);

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            uploadStatus.textContent = data.message || "Upload failed.";
            return;
        }

        uploadStatus.textContent =
            `Indexed ${data.files.length} file(s), ${data.chunks} chunk(s). Database created: ${data.database_created}.`;
    } catch (error) {
        uploadStatus.textContent = "Upload failed. Check the backend terminal.";
    } finally {
        setLoading(uploadButton, false, "Upload and index");
    }
});

askButton.addEventListener("click", async () => {
    const question = questionInput.value.trim();

    if (!question) {
        answerArea.classList.remove("hidden");
        answerText.textContent = "Please enter a question.";
        return;
    }

    answerArea.classList.remove("hidden");
    sourcesArea.classList.add("hidden");
    answerText.textContent = "Thinking...";
    setLoading(askButton, true);

    try {
        const response = await fetch("/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ question })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            answerText.textContent = data.message || "Something went wrong.";
            return;
        }

        answerText.textContent = data.answer || "No answer returned.";
        sourcesList.innerHTML = "";

        if (data.sources && data.sources.length) {
            for (const source of data.sources) {
                const li = document.createElement("li");
                li.textContent = `${source.source} - ${source.location} - score ${source.score}`;
                sourcesList.appendChild(li);
            }

            sourcesArea.classList.remove("hidden");
        }
    } catch (error) {
        answerText.textContent = "Request failed. Check the backend terminal.";
    } finally {
        setLoading(askButton, false, "Ask assistant");
    }
});

resetButton.addEventListener("click", async () => {
    uploadStatus.textContent = "Resetting session...";
    setLoading(resetButton, true);

    try {
        const response = await fetch("/reset", {
            method: "POST"
        });

        const data = await response.json();

        uploadStatus.textContent = data.message || "Session reset.";
        answerArea.classList.add("hidden");
        sourcesArea.classList.add("hidden");
        fileInput.value = "";
        questionInput.value = "";
    } catch (error) {
        uploadStatus.textContent = "Reset failed.";
    } finally {
        setLoading(resetButton, false, "Reset");
    }
});

statusButton.addEventListener("click", refreshStatus);

refreshStatus();
