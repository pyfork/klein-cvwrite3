// Profile upload: show which file was picked, so "Read this file" isn't a guess.
document.querySelectorAll(".drop input[type=file]").forEach(function (input) {
  var drop = input.closest(".drop"), t = drop.querySelector(".drop-t"), s = drop.querySelector(".drop-s");
  var btn = input.form.querySelector("button[type=submit]");
  var t0 = t.textContent, s0 = s.textContent, MAX = 2 * 1024 * 1024;

  function size(n) {
    return n < 1024 * 1024 ? Math.max(1, Math.round(n / 1024)) + " KB" : (n / 1024 / 1024).toFixed(1) + " MB";
  }

  function show() {
    var f = input.files && input.files[0], big = !!f && f.size > MAX;
    drop.classList.toggle("is-picked", !!f && !big);
    drop.classList.toggle("is-too-big", big);
    btn.classList.toggle("btn-primary", !!f && !big);
    btn.classList.toggle("btn-ghost", !f || big);
    btn.disabled = big;
    t.textContent = f ? f.name : t0;
    s.textContent = !f ? s0 : big ? size(f.size) + ": over 2 MB. Choose a smaller file."
                                  : size(f.size) + ". Choose again to use a different file.";
  }

  input.addEventListener("change", show);
  show();  // the browser may keep the file after Back
});
