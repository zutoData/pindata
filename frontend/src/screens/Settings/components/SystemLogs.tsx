import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card } from '../../../components/ui/card';
import { Input } from '../../../components/ui/input';
import { Button } from '../../../components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../components/ui/select";
import { Badge } from "../../../components/ui/badge";
import {
  Download,
  Search,
  Play,
  Pause,
  RefreshCw,
  Loader2,
  AlertCircle,
  Info
} from 'lucide-react';
import { useSystemLogs } from '../../../hooks/useSystemLogs';
import { LogLevel } from '../../../types/systemLog';

export const SystemLogs = (): JSX.Element => {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLevel, setSelectedLevel] = useState<string>('all');
  const [isLogPaused, setIsLogPaused] = useState(false);

  const {
    logs,
    loading: logsLoading,
    error: logsError,
    stats,
    fetchLogs,
    cleanupLogs,
    downloadLogs,
    refreshLogs
  } = useSystemLogs();

  const getLevelColor = (level: LogLevel) => {
    switch (level) {
      case 'error':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'warn':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'info':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'debug':
        return 'text-gray-600 bg-gray-50 border-gray-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getLevelIcon = (level: LogLevel) => {
    switch (level) {
      case 'error':
        return <AlertCircle className="w-4 h-4" />;
      case 'warn':
        return <AlertCircle className="w-4 h-4" />;
      case 'info':
        return <Info className="w-4 h-4" />;
      case 'debug':
        return <Info className="w-4 h-4" />;
      default:
        return <Info className="w-4 h-4" />;
    }
  };

  const filteredLogs = logs.filter(log => {
    const matchesSearch = log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         log.source.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLevel = selectedLevel === 'all' || log.level === selectedLevel;
    return matchesSearch && matchesLevel;
  });

  const handleLogSearch = async () => {
    await fetchLogs({ 
      search: searchQuery,
      level: selectedLevel === 'all' ? undefined : selectedLevel as LogLevel
    });
  };

  const handleExportLogs = async () => {
    try {
      await downloadLogs({
        level: selectedLevel === 'all' ? undefined : selectedLevel as LogLevel,
        search: searchQuery || undefined
      });
    } catch (error) {
      console.error('Failed to export logs:', error);
    }
  };

  const handleCleanupLogs = async () => {
    try {
      await cleanupLogs({ days: 30 });
    } catch (error) {
      console.error('Failed to cleanup logs:', error);
    }
  };

  return (
    <Card className="border-[#d1dbe8]">
      {/* 错误提示 */}
      {logsError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg mb-4">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
            <span className="text-red-800">{logsError}</span>
          </div>
        </div>
      )}

      <div className="p-6 border-b border-[#d1dbe8]">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-[#0c141c]">{t('settings.logs')}</h3>
            {stats && (
              <div className="flex items-center gap-4 mt-2 text-sm text-[#4f7096]">
                <span>{t('settings.totalLogs')}: {stats.total_logs}</span>
                <span>{t('settings.logLevels.error')}: {stats.recent_errors}</span>
                <span>{t('settings.logLevels.info')}: {stats.level_stats?.info || 0}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsLogPaused(!isLogPaused)}
              className="border-[#d1dbe8]"
            >
              {isLogPaused ? (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  {t('settings.logResume')}
                </>
              ) : (
                <>
                  <Pause className="w-4 h-4 mr-2" />
                  {t('settings.logPause')}
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={refreshLogs}
              disabled={logsLoading}
              className="border-[#d1dbe8]"
            >
              {logsLoading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              {t('settings.llm.refresh')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportLogs}
              className="border-[#d1dbe8]"
            >
              <Download className="w-4 h-4 mr-2" />
              {t('settings.exportLogs')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCleanupLogs}
              className="border-[#d1dbe8] text-red-600 hover:text-red-700"
            >
              {t('settings.clearLogs')}
            </Button>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#4f7096] w-4 h-4" />
              <Input
                placeholder={t('settings.searchLogs')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleLogSearch()}
                className="pl-10 border-[#d1dbe8]"
              />
            </div>
          </div>
          
          <Select value={selectedLevel} onValueChange={setSelectedLevel}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('settings.allLevels')}</SelectItem>
              <SelectItem value="error">{t('settings.logLevels.error')}</SelectItem>
              <SelectItem value="warn">{t('settings.logLevels.warn')}</SelectItem>
              <SelectItem value="info">{t('settings.logLevels.info')}</SelectItem>
              <SelectItem value="debug">{t('settings.logLevels.debug')}</SelectItem>
            </SelectContent>
          </Select>

          <Button onClick={handleLogSearch} size="sm">
            <Search className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="p-6">
        {logsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin mr-2" />
            <span>{t('settings.loadingLogs')}</span>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredLogs.map(log => (
              <div key={log.id} className={`p-4 rounded-lg border ${getLevelColor(log.level)}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1">
                    <div className="flex items-center gap-2 mt-0.5">
                      {getLevelIcon(log.level)}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium">{log.message}</span>
                        <Badge variant="outline" className="text-xs">
                          {log.source}
                        </Badge>
                        <Badge 
                          variant="outline" 
                          className={`text-xs ${
                            log.level === 'error' ? 'border-red-500 text-red-700' :
                            log.level === 'warn' ? 'border-yellow-500 text-yellow-700' :
                            log.level === 'info' ? 'border-blue-500 text-blue-700' :
                            'border-gray-500 text-gray-700'
                          }`}
                        >
                          {log.level.toUpperCase()}
                        </Badge>
                      </div>
                      {log.details && (
                        <p className="text-sm opacity-80 mb-2">{log.details}</p>
                      )}
                      <p className="text-xs opacity-60">
                        {new Date(log.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        
        {!logsLoading && filteredLogs.length === 0 && (
          <div className="text-center py-8 text-[#4f7096]">
            {t('settings.noLogs')}
          </div>
        )}
      </div>
    </Card>
  );
}; 