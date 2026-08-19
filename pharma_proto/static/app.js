const provider = document.querySelector("#provider");
const tier = document.querySelector("#tier");
const apiKey = document.querySelector("#api-key");
const question = document.querySelector("#question");
const message = document.querySelector("#message");
const results = document.querySelector("#results");

async function jsonRequest(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "APP-START-001");
  return data;
}

async function refreshHealth() {
  try {
    const data = await jsonRequest("/health");
    document.querySelector("#health").textContent =
      `${data.status} · 앱 ${data.app_version} · DB ${data.snapshot_id} / schema ${data.schema_version}`;
  } catch (error) {
    document.querySelector("#health").textContent = error.message;
  }
}

document.querySelector("#save-key").addEventListener("click", async () => {
  message.textContent = "";
  try {
    await jsonRequest("/api/key", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({provider: provider.value, api_key: apiKey.value}),
    });
    apiKey.value = "";
    message.textContent = "이번 실행에 API 키를 적용했습니다.";
  } catch (error) {
    apiKey.value = "";
    message.textContent = error.message;
  }
});

document.querySelector("#generate").addEventListener("click", async () => {
  message.textContent = "생성 중…";
  results.replaceChildren();
  try {
    const data = await jsonRequest("/api/generate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({provider: provider.value, tier: tier.value, question: question.value}),
    });
    results.innerHTML = data.html;
    message.textContent = "완료";
  } catch (error) {
    message.textContent = error.message;
  }
});

refreshHealth();
