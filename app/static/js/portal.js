/**
 * Northstar University - Student Admission Portal Client Script
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Toast
  Toast.init();

  // Navigation Tabs
  const navLinks = document.querySelectorAll('[data-tab-target]');
  const tabPanes = document.querySelectorAll('.tab-pane');

  function switchTab(targetTabId) {
    tabPanes.forEach(pane => {
      pane.style.display = pane.id === targetTabId ? 'block' : 'none';
    });

    navLinks.forEach(link => {
      if (link.getAttribute('data-tab-target') === targetTabId) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = link.getAttribute('data-tab-target');
      if (targetId) switchTab(targetId);
    });
  });

  // Mobile menu toggle
  const mobileToggle = document.getElementById('mobileToggle');
  const navMenu = document.getElementById('navMenu');
  if (mobileToggle && navMenu) {
    mobileToggle.addEventListener('click', () => {
      navMenu.style.display = navMenu.style.display === 'flex' ? 'none' : 'flex';
    });
  }

  // Program selection shortcuts
  document.querySelectorAll('.btn-select-program').forEach(btn => {
    btn.addEventListener('click', () => {
      const programName = btn.getAttribute('data-program');
      const selectElem = document.querySelector('select[name="program"]');
      if (selectElem && programName) {
        selectElem.value = programName;
      }
      switchTab('tab-apply');
      Toast.show('Program Selected', `You selected ${programName}. Complete your application below.`, 'info');
    });
  });

  // -------------------------------------------------------------
  // Multi-Step Application Wizard Logic
  // -------------------------------------------------------------
  let currentStep = 1;
  const totalSteps = 6;
  const form = document.getElementById('admissionForm');
  const nextBtn = document.getElementById('nextStepBtn');
  const prevBtn = document.getElementById('prevStepBtn');
  const submitBtn = document.getElementById('submitAppBtn');
  const saveDraftBtn = document.getElementById('saveDraftBtn');
  const progressBar = document.getElementById('wizardProgressBar');
  const stepCountIndicator = document.getElementById('stepCountIndicator');

  function updateStepperUI() {
    // Update step containers
    for (let i = 1; i <= totalSteps; i++) {
      const stepElem = document.getElementById(`step-${i}`);
      const navItem = document.getElementById(`step-nav-${i}`);
      if (stepElem) {
        stepElem.classList.toggle('active', i === currentStep);
      }
      if (navItem) {
        navItem.classList.toggle('active', i === currentStep);
        navItem.classList.toggle('completed', i < currentStep);
      }
    }

    // Update buttons
    if (prevBtn) prevBtn.style.display = currentStep === 1 ? 'none' : 'inline-flex';
    if (nextBtn) nextBtn.style.display = currentStep === totalSteps ? 'none' : 'inline-flex';
    if (submitBtn) submitBtn.style.display = currentStep === totalSteps ? 'inline-flex' : 'none';

    // Update progress bar
    const percent = Math.round(((currentStep - 1) / (totalSteps - 1)) * 100);
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (stepCountIndicator) stepCountIndicator.textContent = `Step ${currentStep} of ${totalSteps} (${percent}%)`;

    // If on review step, populate review summary
    if (currentStep === 6) {
      populateReviewSummary();
    }
  }

  function validateCurrentStep() {
    const activeStepElem = document.getElementById(`step-${currentStep}`);
    if (!activeStepElem) return true;

    const inputs = activeStepElem.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    let firstInvalid = null;

    inputs.forEach(input => {
      // Clear previous error styles
      input.classList.remove('error');
      const errSpan = input.parentElement.querySelector('.form-error-msg');
      if (errSpan) errSpan.remove();

      if (!input.checkValidity() || !input.value.trim()) {
        isValid = false;
        input.classList.add('error');
        const msg = document.createElement('span');
        msg.className = 'form-error-msg';
        msg.textContent = input.validationMessage || 'This field is required.';
        input.parentElement.appendChild(msg);
        if (!firstInvalid) firstInvalid = input;
      }
    });

    // Special validation for Statement of Purpose on Step 5
    if (currentStep === 5) {
      const statement = form.querySelector('textarea[name="statement"]');
      if (statement && statement.value.trim().length < 20) {
        isValid = false;
        statement.classList.add('error');
        Toast.show('Validation Error', 'Statement of purpose must be at least 20 characters.', 'warning');
        if (!firstInvalid) firstInvalid = statement;
      }
    }

    if (!isValid && firstInvalid) {
      firstInvalid.focus();
      Toast.show('Missing Information', 'Please complete all required fields on this step.', 'warning');
    }

    return isValid;
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      if (validateCurrentStep()) {
        if (currentStep < totalSteps) {
          currentStep++;
          updateStepperUI();
          autoSaveDraft();
          window.scrollTo({ top: document.getElementById('applySection').offsetTop - 30, behavior: 'smooth' });
        }
      }
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      if (currentStep > 1) {
        currentStep--;
        updateStepperUI();
        window.scrollTo({ top: document.getElementById('applySection').offsetTop - 30, behavior: 'smooth' });
      }
    });
  }

  // Stepper navigation click jump
  document.querySelectorAll('.stepper-item').forEach(item => {
    item.addEventListener('click', () => {
      const targetStep = parseInt(item.getAttribute('data-step') || '1', 10);
      if (targetStep < currentStep) {
        currentStep = targetStep;
        updateStepperUI();
      } else if (targetStep > currentStep) {
        if (validateCurrentStep()) {
          currentStep = targetStep;
          updateStepperUI();
        }
      }
    });
  });

  // Statement char counter
  const statementTextarea = document.getElementById('statementTextarea');
  const charCounter = document.getElementById('statementCharCount');
  if (statementTextarea && charCounter) {
    statementTextarea.addEventListener('input', () => {
      const count = statementTextarea.value.length;
      charCounter.textContent = `${count} / 2000 characters`;
      charCounter.style.color = count < 20 ? 'var(--danger)' : 'var(--text-muted)';
    });
  }

  // LocalStorage Draft Save & Restore
  const DRAFT_KEY = 'northstar_admission_draft';

  function autoSaveDraft() {
    if (!form) return;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data._step = currentStep;
    localStorage.setItem(DRAFT_KEY, JSON.stringify(data));
  }

  function restoreDraft() {
    const saved = localStorage.getItem(DRAFT_KEY);
    if (!saved) return;
    try {
      const data = JSON.parse(saved);
      Object.keys(data).forEach(key => {
        const input = form.querySelector(`[name="${key}"]`);
        if (input && key !== '_step') {
          input.value = data[key];
        }
      });
      if (data._step && data._step > 1 && data._step <= totalSteps) {
        currentStep = data._step;
        updateStepperUI();
      }
      Toast.show('Draft Restored', 'We loaded your previously entered application details.', 'info');
    } catch (_) {}
  }

  if (saveDraftBtn) {
    saveDraftBtn.addEventListener('click', () => {
      autoSaveDraft();
      Toast.show('Draft Saved', 'Your application progress has been saved securely to this device.', 'success');
    });
  }

  // Populate Step 6 Review Summary
  function populateReviewSummary() {
    const summaryCard = document.getElementById('reviewSummaryContent');
    if (!summaryCard || !form) return;

    const data = Object.fromEntries(new FormData(form).entries());

    summaryCard.innerHTML = `
      <div class="d-grid grid-autofit-280 gap-px-20">
        <div class="card p-18 bl-4-solid-brand-blue">
          <h4 class="mb-10 fs-0_95 text-navy-900">1. Personal Information</h4>
          <p class="fs-0_875 lh-1_6 text-secondary">
            <strong>Full Name:</strong> ${esc(data.full_name || '—')}<br>
            <strong>Email:</strong> ${esc(data.email || '—')}<br>
            <strong>Phone:</strong> ${esc(data.phone || '—')}<br>
            <strong>Date of Birth:</strong> ${esc(data.date_of_birth || '—')}<br>
            <strong>Gender:</strong> ${esc(data.gender || 'Not specified')}<br>
            <strong>Nationality:</strong> ${esc(data.nationality || 'Not specified')}
          </p>
        </div>

        <div class="card p-18 bl-4-solid-brand-indigo">
          <h4 class="mb-10 fs-0_95 text-navy-900">2. Academic History</h4>
          <p class="fs-0_875 lh-1_6 text-secondary">
            <strong>Qualification:</strong> ${esc(data.highest_qualification || 'Senior Secondary (12th)')}<br>
            <strong>Institution:</strong> ${esc(data.previous_institution || '—')}<br>
            <strong>Completion Year:</strong> ${esc(data.passing_year || '2026')}<br>
            <strong>Major / Stream:</strong> ${esc(data.academic_stream || 'Science / Math')}<br>
            <strong>Overall GPA / Score:</strong> ${esc(data.gpa_score || '—')}
          </p>
        </div>

        <div class="card p-18 bl-4-solid-success">
          <h4 class="mb-10 fs-0_95 text-navy-900">3. Program Choice</h4>
          <p class="fs-0_875 lh-1_6 text-secondary">
            <strong>Degree Program:</strong> <span class="badge badge-info">${esc(data.program || '—')}</span><br>
            <strong>Intake Term:</strong> ${esc(data.intake_term || 'Fall 2026')}<br>
            <strong>Study Mode:</strong> ${esc(data.study_mode || 'Full-time On-Campus')}<br>
            <strong>Scholarship Request:</strong> ${data.scholarship_interest ? 'Yes' : 'No'}
          </p>
        </div>

        <div class="card p-18 bl-4-solid-warning">
          <h4 class="mb-10 fs-0_95 text-navy-900">4. Contact Address</h4>
          <p class="fs-0_875 lh-1_6 text-secondary">
            <strong>Street Address:</strong> ${esc(data.street_address || '—')}<br>
            <strong>City:</strong> ${esc(data.city || '—')}<br>
            <strong>State / Province:</strong> ${esc(data.state || '—')}<br>
            <strong>Country:</strong> ${esc(data.country || '—')}<br>
            <strong>Emergency Contact:</strong> ${esc(data.emergency_contact || '—')}
          </p>
        </div>
      </div>

      <div class="card mt-18 p-18 bg-card-subtle">
        <h4 class="mb-8 fs-0_95 text-navy-900">Personal Statement</h4>
        <p class="fs-0_875 text-secondary font-italic ws-pre-wrap">
          "${esc(data.statement || 'No statement provided.')}"
        </p>
      </div>
    `;
  }

  // Handle Final Submission
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const declarationCheck = document.getElementById('declarationCheck');
      if (declarationCheck && !declarationCheck.checked) {
        Toast.show('Confirmation Required', 'Please accept the honor code and declaration before submitting.', 'warning');
        declarationCheck.focus();
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = `
        <svg class="animate-pulse w-18px h-18px mr-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" stroke-opacity="0.3"></circle>
          <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"></path>
        </svg>
        Securing & Submitting…
      `;

      try {
        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());

        const result = await Api.submitApplication(payload);

        // Clear local draft
        localStorage.removeItem(DRAFT_KEY);

        // Show Submission Confirmation Modal
        showSubmissionReceipt(result, payload);

        // Store reference in local storage for quick status checks
        localStorage.setItem('northstar_last_ref', result.reference_code);
        localStorage.setItem('northstar_last_email', payload.email);

        // Also update the Student Dashboard with these details
        updateStudentDashboard({
          reference_code: result.reference_code,
          program: payload.program,
          full_name: payload.full_name,
          email: payload.email,
          status: result.action === 'allow' ? 'Application received' : (result.action === 'captcha' ? 'Verification required' : 'Held for review'),
          raw_status: result.action,
          submitted_at: result.created_at || new Date().toISOString()
        });

        Toast.show('Application Submitted!', `Your reference code is ${result.reference_code}`, 'success');

      } catch (err) {
        Toast.show('Submission Error', err.message || 'We could not submit your application. Please check the fields.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Submit Application';
      }
    });
  }

  // Show official receipt modal
  function showSubmissionReceipt(result, payload) {
    const modal = document.getElementById('receiptModal');
    if (!modal) return;

    document.getElementById('receiptRefCode').textContent = result.reference_code;
    document.getElementById('receiptStudentName').textContent = payload.full_name;
    document.getElementById('receiptProgram').textContent = payload.program;
    document.getElementById('receiptEmail').textContent = payload.email;
    document.getElementById('receiptDate').textContent = new Date().toLocaleString();

    const statusBadge = document.getElementById('receiptStatusBadge');
    if (result.action === 'allow') {
      statusBadge.className = 'badge badge-success';
      statusBadge.innerHTML = '<span class="badge-dot"></span> Official Submission Cleared';
      document.getElementById('receiptActionNotice').innerHTML = `
        <strong>Security Clearance Verified:</strong> Your application successfully passed automatic security verification. Our admissions faculty will now review your academic dossier.
      `;
    } else if (result.action === 'captcha') {
      statusBadge.className = 'badge badge-warning';
      statusBadge.innerHTML = '<span class="badge-dot"></span> Additional Verification Required';
      document.getElementById('receiptActionNotice').innerHTML = `
        <strong>Secondary Verification:</strong> A verification request has been queued to confirm your submission credentials. Please check your email for any follow-up verification steps.
      `;
    } else {
      statusBadge.className = 'badge badge-danger';
      statusBadge.innerHTML = '<span class="badge-dot"></span> Compliance Screening';
      document.getElementById('receiptActionNotice').innerHTML = `
        <strong>Compliance Review:</strong> Your submission has been flagged for manual verification by the admissions board. Keep your reference code safe for future correspondence.
      `;
    }

    modal.classList.add('active');
  }

  // Close receipt modal
  document.getElementById('closeReceiptBtn')?.addEventListener('click', () => {
    document.getElementById('receiptModal')?.classList.remove('active');
    switchTab('tab-dashboard');
  });

  // Print receipt
  document.getElementById('printReceiptBtn')?.addEventListener('click', () => {
    window.print();
  });

  // Copy reference code button
  document.getElementById('copyRefBtn')?.addEventListener('click', () => {
    const ref = document.getElementById('receiptRefCode')?.textContent;
    if (ref) {
      navigator.clipboard.writeText(ref).then(() => {
        Toast.show('Copied!', 'Application reference code copied to clipboard.', 'success');
      });
    }
  });

  // -------------------------------------------------------------
  // Application Status Tracking Logic
  // -------------------------------------------------------------
  const statusForm = document.getElementById('statusCheckForm');
  const statusResultContainer = document.getElementById('statusResultContainer');

  if (statusForm) {
    // Pre-fill last ref if available
    const lastRef = localStorage.getItem('northstar_last_ref');
    const lastEmail = localStorage.getItem('northstar_last_email');
    if (lastRef) statusForm.querySelector('input[name="reference_code"]').value = lastRef;
    if (lastEmail) statusForm.querySelector('input[name="email"]').value = lastEmail;

    statusForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const refInput = statusForm.querySelector('input[name="reference_code"]');
      const emailInput = statusForm.querySelector('input[name="email"]');
      const checkBtn = statusForm.querySelector('button[type="submit"]');

      checkBtn.disabled = true;
      checkBtn.textContent = 'Searching Records…';

      try {
        const data = await Api.getApplicationStatus(refInput.value.trim(), emailInput.value.trim());
        renderStatusTimeline(data);
        updateStudentDashboard(data);
        Toast.show('Application Found', `Status: ${data.status}`, 'success');
      } catch (err) {
        statusResultContainer.innerHTML = `
          <div class="card bl-4-solid-danger p-20 text-center">
            <svg class="w-44px h-44px text-danger center-mb-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
            <h4 class="text-navy-900 mb-6">Application Not Found</h4>
            <p class="fs-0_9 text-secondary">${esc(err.message || 'Please check your Reference Code and Email address.')}</p>
          </div>
        `;
        Toast.show('Not Found', err.message || 'No application matches that reference and email.', 'error');
      } finally {
        checkBtn.disabled = false;
        checkBtn.textContent = 'Track Application';
      }
    });
  }

  function renderStatusTimeline(appData) {
    if (!statusResultContainer) return;

    const submittedDate = appData.submitted_at ? new Date(appData.submitted_at + (appData.submitted_at.includes('Z') ? '' : 'Z')).toLocaleString() : 'Recent';
    const isAllowed = appData.raw_status === 'allow' || appData.status.includes('received') || appData.status.includes('Approved');
    const isCaptcha = appData.raw_status === 'captcha' || appData.status.includes('Verification');
    const isBlocked = appData.raw_status === 'block' || appData.status.includes('review') || appData.status.includes('held');

    let badgeClass = isAllowed ? 'badge-success' : (isCaptcha ? 'badge-warning' : 'badge-danger');

    statusResultContainer.innerHTML = `
      <div class="card shadow-md mt-24">
        <div class="card-header wrap-wrap gap-px-12">
          <div>
            <span class="badge ${badgeClass} mb-8">
              <span class="badge-dot"></span> ${esc(appData.status)}
            </span>
            <h3 class="fs-1_35 text-navy-900">${esc(appData.program || 'Undergraduate Admission')}</h3>
            <p class="fs-0_85 text-muted">
              Candidate: <strong>${esc(appData.full_name || 'Applicant')}</strong> · Reference: <strong class="font-mono text-brand-blue">${esc(appData.reference_code)}</strong>
            </p>
          </div>
          <div>
            <button class="btn btn-secondary btn-sm" onclick="window.print()">
              <svg class="w-16px h-16px" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" /></svg>
              Print Slip
            </button>
          </div>
        </div>

        <div class="status-timeline">
          <!-- Step 1 -->
          <div class="timeline-step completed">
            <div class="timeline-dot">✓</div>
            <div class="timeline-step-content">
              <div class="flex items-center justify-between">
                <strong class="text-navy-900">Application Submitted</strong>
                <span class="fs-0_775 text-muted">${submittedDate}</span>
              </div>
              <p class="fs-0_825 text-secondary mt-4">
                Online registration completed and application reference code generated.
              </p>
            </div>
          </div>

          <!-- Step 2 -->
          <div class="timeline-step ${isAllowed ? 'completed' : 'active'}">
            <div class="timeline-dot">${isAllowed ? '✓' : '●'}</div>
            <div class="timeline-step-content">
              <div class="flex items-center justify-between">
                <strong class="text-navy-900">Security & Duplicate Clearance</strong>
                <span class="badge ${isAllowed ? 'badge-success' : 'badge-warning'}">${isAllowed ? 'Passed' : 'Under Review'}</span>
              </div>
              <p class="fs-0_825 text-secondary mt-4">
                Automatic security check for duplicate registrations and velocity rate-limiting.
              </p>
            </div>
          </div>

          <!-- Step 3 -->
          <div class="timeline-step ${isAllowed ? 'active' : ''}">
            <div class="timeline-dot">3</div>
            <div class="timeline-step-content">
              <div class="flex items-center justify-between">
                <strong class="text-navy-900">Academic Credentials & Document Verification</strong>
                <span class="badge badge-neutral">In Queue</span>
              </div>
              <p class="fs-0_825 text-secondary mt-4">
                Admissions officers are verifying official high school transcripts and identity proof.
              </p>
            </div>
          </div>

          <!-- Step 4 -->
          <div class="timeline-step">
            <div class="timeline-dot">4</div>
            <div class="timeline-step-content">
              <div class="flex items-center justify-between">
                <strong class="text-navy-900">Faculty Departmental Review</strong>
                <span class="badge badge-neutral">Upcoming</span>
              </div>
              <p class="fs-0_825 text-secondary mt-4">
                Department Admissions Committee evaluates statement of purpose and academic stream qualifications.
              </p>
            </div>
          </div>

          <!-- Step 5 -->
          <div class="timeline-step">
            <div class="timeline-dot">5</div>
            <div class="timeline-step-content">
              <div class="flex items-center justify-between">
                <strong class="text-navy-900">Final Admission Decision & Offer Letter</strong>
                <span class="badge badge-neutral">Pending</span>
              </div>
              <p class="fs-0_825 text-secondary mt-4">
                Formal offer of admission and registration packet dispatched to candidate email.
              </p>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Update Student Dashboard view
  function updateStudentDashboard(data) {
    const dashRef = document.getElementById('dashAppRef');
    const dashProgram = document.getElementById('dashAppProgram');
    const dashStatus = document.getElementById('dashAppStatus');
    const dashDate = document.getElementById('dashAppDate');

    if (dashRef && data.reference_code) dashRef.textContent = data.reference_code;
    if (dashProgram && data.program) dashProgram.textContent = data.program;
    if (dashStatus && data.status) dashStatus.textContent = data.status;
    if (dashDate && data.submitted_at) dashDate.textContent = new Date(data.submitted_at).toLocaleDateString();

    const progressFill = document.getElementById('dashProgressFill');
    if (progressFill) {
      progressFill.style.width = data.raw_status === 'allow' ? '70%' : '40%';
    }
  }

  // -------------------------------------------------------------
  // Document Vault Logic (Upload Simulation & Storage)
  // -------------------------------------------------------------
  const dropzone = document.getElementById('docDropzone');
  const fileInput = document.getElementById('fileUploadInput');
  const uploadedDocsList = document.getElementById('uploadedDocsList');

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length) {
        handleFileUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) {
        handleFileUpload(fileInput.files[0]);
      }
    });
  }

  function handleFileUpload(file) {
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      Toast.show('File Too Large', 'Maximum allowed file size is 10MB.', 'error');
      return;
    }

    Toast.show('Uploading Document', `Uploading ${file.name}…`, 'info');

    // Simulate upload progress
    const docItem = document.createElement('div');
    docItem.className = 'doc-item-card';
    const docId = 'doc-' + Date.now();
    docItem.id = docId;

    docItem.innerHTML = `
      <div class="flex items-center gap-3">
        <div class="w-40px h-40px bg-brand-blue-tint-bg radius-8 d-flex items-center justify-center text-brand-blue">
          <svg class="w-22px h-22px" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
        </div>
        <div>
          <strong class="fs-0_9 text-navy-900 d-block">${esc(file.name)}</strong>
          <span class="fs-0_775 text-muted">${(file.size / 1024).toFixed(1)} KB · Just now</span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span class="badge badge-success"><span class="badge-dot"></span> Uploaded</span>
        <button class="btn btn-ghost btn-sm" onclick="document.getElementById('${docId}').remove(); Toast.show('File Removed', 'Document deleted.', 'info');">
          <svg class="w-16px h-16px text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
        </button>
      </div>
    `;

    if (uploadedDocsList) {
      uploadedDocsList.prepend(docItem);
    }

    setTimeout(() => {
      Toast.show('Document Uploaded', `${file.name} was successfully stored in your Document Vault.`, 'success');
    }, 600);
  }

  // Restore draft on initial load
  restoreDraft();
  updateStepperUI();
});
