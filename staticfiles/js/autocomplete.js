// static/js/autocomplete.js
// CYON Harvest - Smart Autocomplete

document.addEventListener('DOMContentLoaded', () => {
    const nameInput = document.getElementById('name');
    if (!nameInput) return;

    let resultsDiv = document.getElementById('autocomplete-results');
    if (!resultsDiv) {
        resultsDiv = document.createElement('div');
        resultsDiv.id = 'autocomplete-results';
        resultsDiv.style.cssText = 'display: none; position: absolute; top: 100%; left: 0; right: 0; background: var(--card-bg, #1e293b); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; z-index: 10; max-height: 200px; overflow-y: auto; backdrop-filter: blur(12px); box-shadow: 0 10px 15px rgba(0,0,0,0.3);';
        
        // Ensure parent has position relative
        nameInput.parentNode.style.position = 'relative';
        nameInput.parentNode.insertBefore(resultsDiv, nameInput.nextSibling);
    }

    let titleOptionsDiv = document.getElementById('title-options-container');
    if (!titleOptionsDiv) {
        titleOptionsDiv = document.createElement('div');
        titleOptionsDiv.id = 'title-options-container';
        titleOptionsDiv.style.cssText = 'display: none; margin-top: 10px; gap: 8px; flex-wrap: wrap;';
        nameInput.parentNode.appendChild(titleOptionsDiv);
    }

    function hideTitleOptions() {
        titleOptionsDiv.style.display = 'none';
    }

    function showTitleOptions(fullName, inputEl) {
        let baseName = fullName.replace(/Mr\s*&\s*Mrs\.?/i, '').replace(/Mr\.\s*&\s*Mrs\.?/i, '').replace(/Mr\s+and\s+Mrs\.?/i, '').trim();
        
        const options = [
            `Mr. ${baseName}`,
            `Mrs. ${baseName}`,
            fullName
        ];
        
        titleOptionsDiv.innerHTML = '<span style="font-size: 0.8rem; color: #C9A227; width: 100%; display: block; margin-bottom: 4px;">Donate as:</span>';
        options.forEach(opt => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = opt;
            btn.style.cssText = 'background: rgba(201,162,39,0.1); border: 1px solid rgba(201,162,39,0.5); color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; cursor: pointer; transition: all 0.2s;';
            btn.addEventListener('mouseenter', () => btn.style.background = 'rgba(201,162,39,0.3)');
            btn.addEventListener('mouseleave', () => btn.style.background = 'rgba(201,162,39,0.1)');
            btn.addEventListener('click', () => {
                inputEl.value = opt;
                hideTitleOptions();
                const amountInput = document.getElementById('display_amount');
                if (amountInput) amountInput.focus();
            });
            titleOptionsDiv.appendChild(btn);
        });
        titleOptionsDiv.style.display = 'flex';
    }

    let searchTimeout = null;

    nameInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        hideTitleOptions();
        const query = nameInput.value.trim();

        if (query.length < 2) {
            resultsDiv.style.display = 'none';
            return;
        }

        searchTimeout = setTimeout(async () => {
            try {
                const response = await fetch(`/api/names/search/?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                
                if (data.length > 0) {
                    resultsDiv.innerHTML = data.map(name => `
                        <div class="suggestion-item" data-name="${name.replace(/"/g, '&quot;')}" style="padding: 10px 15px; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;">
                            ${name}
                        </div>
                    `).join('');
                    resultsDiv.style.display = 'block';

                    // Attach click handlers
                    const items = resultsDiv.querySelectorAll('.suggestion-item');
                    items.forEach(item => {
                        item.addEventListener('click', () => {
                            const selectedName = item.getAttribute('data-name');
                            nameInput.value = selectedName;
                            resultsDiv.style.display = 'none';
                            
                            const lcName = selectedName.toLowerCase();
                            if (lcName.includes('mr & mrs') || lcName.includes('mr. & mrs.') || lcName.includes('mr and mrs')) {
                                showTitleOptions(selectedName, nameInput);
                            } else {
                                // Move focus to amount
                                const amountInput = document.getElementById('display_amount');
                                if (amountInput) amountInput.focus();
                            }
                        });
                        item.addEventListener('mouseenter', () => item.style.backgroundColor = 'rgba(255,255,255,0.1)');
                        item.addEventListener('mouseleave', () => item.style.backgroundColor = 'transparent');
                    });
                } else {
                    resultsDiv.style.display = 'none';
                }
            } catch (e) {
                console.error("Search failed", e);
            }
        }, 300); // 300ms debounce
    });

    // Close on Escape
    nameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            resultsDiv.style.display = 'none';
        }
    });

    // Close if clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.form-group')) {
            resultsDiv.style.display = 'none';
        }
    });
});
