function apiHandler() {
    return {
        apiType: 'native',
        fileName: '',
        cols: [],
        mappings: [{ apiKey: 'description', colName: '' }],
        params: [],
        headers: [{ key: 'Content-Type', value: 'application/json' }],
        isFileLoading: false,
        isProcessing: false,

        // New init function to watch for mode changes
        init() {
            this.$watch('apiType', (val) => {
                if (value === 'native') {
                    this.mappings = [{ apiKey: 'description', colName: '' }];
                } else {
                    this.mappings = [{ apiKey: '', colName: '' }];
                }
            });
        },

        addParam() { this.params.push({ key: '', value: '' }) },
        removeParam(index) { this.params.splice(index, 1) },

        addMapping() { this.mappings.push({ apiKey: '', colName: '' }) },
        removeMapping(index) { this.mappings.splice(index, 1) },

        isMappingValid() {
            return this.mappings.every(m => m.apiKey.trim() !== '' && m.colName !== '');
        },

        onFilePicked(e) {
            const file = e.target.files[0];
            if (!file) return;
            // Maintain the 'description' key if in native mode during reset
            this.mappings = this.apiType === 'native' ? [{ apiKey: 'description', colName: '' }] : [{ apiKey: '', colName: '' }];
            this.isFileLoading = true;
            this.fileName = file.name;
            const extension = file.name.split('.').pop().toLowerCase();
            const reader = new FileReader();
            reader.onload = (ev) => {
                if (extension === 'csv') {
                    const text = ev.target.result;
                    const firstLine = text.split('\n')[0];
                    this.cols = firstLine.split(',').map(c => c.trim().replace(/"/g, ''));
                } else {
                    const data = new Uint8Array(ev.target.result);
                    const workbook = XLSX.read(data, { type: 'array' });
                    const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                    const json = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
                    this.cols = json[0] || [];
                }
                this.isFileLoading = false;
            };
            if (extension === 'csv') reader.readAsText(file.slice(0, 10000));
            else reader.readAsArrayBuffer(file);
        },

        async submitForm(e) {
            this.isProcessing = true;
            const formData = new FormData(e.target);
            formData.append('mapping_data', JSON.stringify(this.mappings));
            try {
                const response = await fetch('/process', { method: 'POST', body: formData });
                if (!response.ok) throw new Error(await response.text());
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = "api_results.xlsx";
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
            } catch (error) {
                alert("Processing Error: " + error.message);
            } finally {
                this.isProcessing = false;
            }
        }
    }
}