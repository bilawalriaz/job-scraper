import { useState, useEffect, useCallback } from 'react';
import { getConfigs, createConfig, updateConfig, deleteConfig } from '../api/client';
import { Card } from '../components/Card';
import { Table, TableHead, TableBody, TableRow, TableHeader, TableCell } from '../components/Table';
import Button from '../components/Button';
import Modal from '../components/Modal';
import Spinner from '../components/Spinner';
import { ActiveBadge, TypeBadge } from '../components/StatusBadge';
import { PlusIcon, EditIcon, DeleteIcon, SearchIcon } from '../components/Icons';

function ConfigForm({ config, onSave, onCancel, saving }) {
    const [form, setForm] = useState({
        name: config?.name || '',
        keywords: config?.keywords || '',
        location: config?.location || '',
        radius: config?.radius || 25,
        employment_types: config?.employment_types || '',
        enabled: config?.enabled ?? true
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        onSave(form);
    };

    return (
        <form onSubmit={handleSubmit}>
            <div className="form-group">
                <label className="form-label">Name</label>
                <input
                    type="text"
                    className="form-control"
                    value={form.name}
                    onChange={(e) => setForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="e.g., Senior Developer Roles"
                    required
                />
            </div>
            <div className="form-group">
                <label className="form-label">Keywords</label>
                <input
                    type="text"
                    className="form-control"
                    value={form.keywords}
                    onChange={(e) => setForm(prev => ({ ...prev, keywords: e.target.value }))}
                    placeholder="e.g., python developer"
                    required
                />
            </div>
            <div className="form-group">
                <label className="form-label">Location</label>
                <input
                    type="text"
                    className="form-control"
                    value={form.location}
                    onChange={(e) => setForm(prev => ({ ...prev, location: e.target.value }))}
                    placeholder="e.g., London"
                    required
                />
            </div>
            <div className="form-group">
                <label className="form-label">Radius (miles)</label>
                <input
                    type="number"
                    className="form-control"
                    value={form.radius}
                    onChange={(e) => setForm(prev => ({ ...prev, radius: parseInt(e.target.value) || 25 }))}
                    min="1"
                    max="100"
                />
            </div>
            <div className="form-group">
                <label className="form-label">Employment Type</label>
                <select
                    className="form-select"
                    value={form.employment_types}
                    onChange={(e) => setForm(prev => ({ ...prev, employment_types: e.target.value }))}
                >
                    <option value="">All Types</option>
                    <option value="contract">Contract</option>
                    <option value="permanent">Permanent</option>
                    <option value="wfh">Remote / Work From Home</option>
                    <option value="temporary">Temporary</option>
                    <option value="part-time">Part-time</option>
                </select>
            </div>
            <div className="form-group">
                <label className="checkbox-label">
                    <input
                        type="checkbox"
                        checked={form.enabled}
                        onChange={(e) => setForm(prev => ({ ...prev, enabled: e.target.checked }))}
                    />
                    Enabled
                </label>
            </div>
            <div className="d-flex gap-3 justify-end">
                <Button variant="secondary" type="button" onClick={onCancel}>
                    Cancel
                </Button>
                <Button variant="primary" type="submit" loading={saving}>
                    {config ? 'Update' : 'Create'}
                </Button>
            </div>
        </form>
    );
}

function Configs() {
    const [configs, setConfigs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [modalOpen, setModalOpen] = useState(false);
    const [editingConfig, setEditingConfig] = useState(null);

    const loadConfigs = useCallback(async () => {
        try {
            const data = await getConfigs();
            setConfigs(data.configs || []);
        } catch (error) {
            console.error('Failed to load configs:', error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadConfigs();
    }, [loadConfigs]);

    const handleOpenCreate = () => {
        setEditingConfig(null);
        setModalOpen(true);
    };

    const handleOpenEdit = (config) => {
        setEditingConfig(config);
        setModalOpen(true);
    };

    const handleSave = async (formData) => {
        setSaving(true);
        try {
            if (editingConfig) {
                await updateConfig(editingConfig.id, formData);
            } else {
                await createConfig(formData);
            }
            setModalOpen(false);
            loadConfigs();
        } catch (error) {
            console.error('Failed to save config:', error);
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Delete this search configuration?')) return;

        try {
            await deleteConfig(id);
            setConfigs(prev => prev.filter(c => c.id !== id));
        } catch (error) {
            console.error('Failed to delete config:', error);
        }
    };

    return (
        <>
            {/* Page Header */}
            <div className="page-header">
                <div>
                    <h1 className="page-title">Search Configurations</h1>
                    <p className="page-subtitle">Manage your automated job search queries</p>
                </div>
                <Button variant="primary" onClick={handleOpenCreate}>
                    <PlusIcon /> Add New Search
                </Button>
            </div>

            {/* Remote Jobs Help */}
            <Card style={{ marginBottom: '1.5rem', background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)', border: '1px solid #f59e0b' }}>
                <div style={{ padding: '1rem' }}>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#92400e', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span>🏠</span> Finding Remote / Work From Home Jobs
                    </h3>
                    <div style={{ fontSize: '0.85rem', color: '#78350f', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
                        <div>
                            <strong>TotalJobs:</strong> Select "Remote / Work From Home" type above
                        </div>
                        <div>
                            <strong>Indeed:</strong> Add "remote" to keywords or use "Remote" as location
                        </div>
                        <div>
                            <strong>Reed:</strong> Add "remote" to keywords or use "Remote" as location
                        </div>
                        <div>
                            <strong>CV-Library:</strong> Use "Remote" as location
                        </div>
                    </div>
                </div>
            </Card>

            {/* Configs Table */}
            <Card>
                {loading ? (
                    <div className="loading-state">
                        <Spinner size={40} />
                    </div>
                ) : configs.length > 0 ? (
                    <Table>
                        <TableHead>
                            <TableRow>
                                <TableHeader>Name</TableHeader>
                                <TableHeader>Keywords</TableHeader>
                                <TableHeader>Location</TableHeader>
                                <TableHeader>Type</TableHeader>
                                <TableHeader>Radius</TableHeader>
                                <TableHeader>Status</TableHeader>
                                <TableHeader>Actions</TableHeader>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {configs.map(config => (
                                <TableRow key={config.id}>
                                    <TableCell>
                                        <strong>{config.name}</strong>
                                    </TableCell>
                                    <TableCell>
                                        <code>{config.keywords}</code>
                                    </TableCell>
                                    <TableCell>{config.location}</TableCell>
                                    <TableCell>
                                        <TypeBadge type={config.employment_types} />
                                    </TableCell>
                                    <TableCell>{config.radius} miles</TableCell>
                                    <TableCell>
                                        <ActiveBadge active={config.enabled} />
                                    </TableCell>
                                    <TableCell>
                                        <div className="d-flex gap-2">
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => handleOpenEdit(config)}
                                            >
                                                <EditIcon size={14} />
                                            </Button>
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                style={{ color: '#ef4444' }}
                                                onClick={() => handleDelete(config.id)}
                                            >
                                                <DeleteIcon size={14} />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                ) : (
                    <div className="empty-state">
                        <SearchIcon size={48} />
                        <div style={{ marginTop: '16px' }}>
                            <p style={{ fontSize: '1rem', marginBottom: '8px' }}>No search configurations yet</p>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                                Create your first search to start tracking jobs
                            </p>
                        </div>
                        <Button variant="primary" onClick={handleOpenCreate} style={{ marginTop: '16px' }}>
                            <PlusIcon /> Add Your First Search
                        </Button>
                    </div>
                )}
            </Card>

            {/* Config Modal */}
            <Modal
                isOpen={modalOpen}
                onClose={() => setModalOpen(false)}
                title={editingConfig ? 'Edit Search Configuration' : 'New Search Configuration'}
            >
                <ConfigForm
                    config={editingConfig}
                    onSave={handleSave}
                    onCancel={() => setModalOpen(false)}
                    saving={saving}
                />
            </Modal>
        </>
    );
}

export default Configs;
