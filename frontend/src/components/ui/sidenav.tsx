import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  DatabaseIcon,
  HardDriveIcon,
  LayoutDashboardIcon,
  ListTodoIcon,
  PuzzleIcon,
  SettingsIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  UserIcon,
  LogOutIcon,
  ShieldCheckIcon,
} from 'lucide-react';
import { Button } from './button';
import { LanguageSwitcher } from './language-switcher';
import { useAuthStore } from '../../store/authStore';

interface SidenavProps {
  onCollapsedChange?: (isCollapsed: boolean) => void;
}

interface SubMenuItem {
  label: string;
  path: string;
  badge?: string;
}

interface NavigationItem {
  icon: React.ReactNode;
  label: string;
  page: string;
  path: string;
  subItems?: SubMenuItem[];
}

export const Sidenav = ({ onCollapsedChange }: SidenavProps): JSX.Element => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedItems, setExpandedItems] = useState<string[]>(['datasets']);
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isLoading } = useAuthStore();

  useEffect(() => {
    onCollapsedChange?.(isCollapsed);
  }, [isCollapsed, onCollapsedChange]);

  const handleToggleCollapse = () => {
    setIsCollapsed(prev => !prev);
  };

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/auth/login');
    } catch (error) {
      console.error('Logout failed:', error);
      // 即使登出失败也要跳转到登录页
      navigate('/auth/login');
    }
  };

  const toggleItemExpansion = (itemPage: string) => {
    setExpandedItems(prev => 
      prev.includes(itemPage) 
        ? prev.filter(item => item !== itemPage)
        : [...prev, itemPage]
    );
  };

  const getCurrentPage = () => {
    const path = location.pathname;
    if (path.startsWith('/datasets')) return 'datasets';
    if (path.startsWith('/rawdata')) return 'rawData';
    if (path.startsWith('/tasks')) return 'tasks';
    if (path.startsWith('/plugins')) return 'plugins';
    if (path.startsWith('/settings')) return 'settings';
    if (path.startsWith('/governance')) return 'governance';
    if (path.startsWith('/overview')) return 'overview';
    return 'overview';
  };

  const currentPage = getCurrentPage();

  const navigationItems = [
    {
      icon: <LayoutDashboardIcon size={24} />,
      label: t('navigation.overview'),
      page: 'overview',
      path: '/overview',
    },
    {
      icon: <DatabaseIcon size={24} />,
      label: t('navigation.datasets'),
      page: 'datasets',
      path: '/datasets',
      subItems: [
        {
          label: t('datasets.title'),
          path: '/datasets',
        },
        {
          label: t('datasets.create.title'),
          path: '/datasets/create',
        },
        {
          label: t('datasets.smartCreate'),
          path: '/datasets/create-smart',
          badge: 'AI'
        }
      ]
    },
    {
      icon: <ListTodoIcon size={24} />,
      label: t('navigation.tasks'),
      page: 'tasks',
      path: '/tasks',
    },
    {
      icon: <HardDriveIcon size={24} />,
      label: t('navigation.rawData'),
      page: 'rawData',
      path: '/rawdata',
    },
    {
      icon: <PuzzleIcon size={24} />,
      label: t('navigation.plugins'),
      page: 'plugins',
      path: '/plugins',
    },
    // {
    //   icon: <ShieldCheckIcon size={24} />,
    //   label: t('navigation.governance'),
    //   page: 'governance',
    //   path: '/governance',
    // },
    {
      icon: <SettingsIcon size={24} />,
      label: t('navigation.settings'),
      page: 'settings',
      path: '/settings',
    },
  ];

  return (
    <nav 
      className={`h-screen bg-[#f7f9fc] flex flex-col transition-all duration-300 ease-in-out shadow-lg ${
        isCollapsed ? 'w-16' : 'w-[300px]'
      }`}
      data-collapsed={isCollapsed}
    >
      <div className="flex-1 p-4">
        <div className="flex flex-col gap-4 w-full">
          <div className="w-full">
            <h2 className={`font-medium text-base text-[#0c141c] leading-6 transition-opacity duration-300 ${
              isCollapsed ? 'opacity-0 pointer-events-none' : 'opacity-100'
            }`}>
              {t('common.appName')}
            </h2>
          </div>

          <div className="flex flex-col gap-2 w-full">
            {navigationItems.map((item) => (
              <div key={item.page} className="w-full">
                <Button
                  variant={currentPage === item.page ? 'secondary' : 'ghost'}
                  className={`flex ${isCollapsed ? 'justify-center' : 'justify-between'} gap-3 px-3 py-2 h-auto w-full transition-all duration-300 ${
                    currentPage === item.page ? 'bg-[#e8edf2]' : ''
                  }`}
                  onClick={() => {
                    if (item.subItems && !isCollapsed) {
                      toggleItemExpansion(item.page);
                    } else {
                      navigate(item.path);
                    }
                  }}
                  title={isCollapsed ? item.label : undefined}
                >
                  <div className="flex items-center gap-3">
                    <span className="w-6 flex-shrink-0">{item.icon}</span>
                    <span className={`font-medium text-sm text-[#0c141c] leading-[21px] transition-all duration-300 ${
                      isCollapsed ? 'opacity-0 w-0 overflow-hidden' : 'opacity-100 w-auto'
                    }`}>
                      {item.label}
                    </span>
                  </div>
                  {item.subItems && !isCollapsed && (
                    <span className="w-4 flex-shrink-0">
                      {expandedItems.includes(item.page) ? 
                        <ChevronUpIcon size={16} /> : 
                        <ChevronDownIcon size={16} />
                      }
                    </span>
                  )}
                </Button>
                
                {/* 子菜单 */}
                {item.subItems && !isCollapsed && expandedItems.includes(item.page) && (
                  <div className="ml-6 mt-1 space-y-1">
                    {item.subItems.map((subItem) => (
                      <Button
                        key={subItem.path}
                        variant="ghost"
                        className={`flex justify-start gap-2 px-3 py-1.5 h-auto w-full text-left transition-all duration-300 ${
                          location.pathname === subItem.path ? 'bg-[#e8edf2] text-[#1977e5]' : 'text-[#4f7096] hover:bg-[#f0f4f8]'
                        }`}
                        onClick={() => navigate(subItem.path)}
                      >
                        <span className="font-medium text-xs leading-[18px]">
                          {subItem.label}
                        </span>
                        {subItem.badge && (
                          <span className="px-1.5 py-0.5 bg-[#1977e5] text-white text-xs rounded-full">
                            {subItem.badge}
                          </span>
                        )}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="p-4 border-t border-[#d1dbe8]">
        {/* 用户信息 */}
        <div className={`mb-3 transition-all duration-300 ${
          isCollapsed ? 'opacity-0 h-0 overflow-hidden' : 'opacity-100 h-auto'
        }`}>
          {user && (
            <div className="bg-[#f0f4f8] rounded-lg p-3 mb-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-[#1977e5] rounded-full flex items-center justify-center">
                  <UserIcon size={16} className="text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[#0c141c] truncate">
                    {user.full_name || user.username}
                  </p>
                  <p className="text-xs text-[#4f7096] truncate">
                    {user.email}
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                className="w-full mt-2 justify-start gap-2 text-[#4f7096] hover:bg-[#e8edf2] h-8"
                onClick={handleLogout}
                disabled={isLoading}
              >
                <LogOutIcon size={14} />
                <span className="text-xs">
                  {isLoading ? t('auth.logout.loggingOut', '登出中...') : t('auth.logout.button', '登出')}
                </span>
              </Button>
            </div>
          )}
          <LanguageSwitcher />
        </div>

        {/* 展开/收起按钮 */}
        <Button
          variant="ghost"
          className="w-full justify-center hover:bg-[#e8edf2] transition-colors duration-200"
          onClick={handleToggleCollapse}
          title={isCollapsed ? t('navigation.expand') : t('navigation.collapse')}
        >
          {isCollapsed ? <ChevronRightIcon size={20} /> : <ChevronLeftIcon size={20} />}
        </Button>

        {/* 收起状态下的用户头像和登出按钮 */}
        {isCollapsed && user && (
          <div className="mt-3 space-y-2">
            <div className="w-8 h-8 bg-[#1977e5] rounded-full flex items-center justify-center mx-auto">
              <UserIcon size={16} className="text-white" />
            </div>
            <Button
              variant="ghost"
              className="w-full p-2 hover:bg-[#e8edf2] transition-colors duration-200"
              onClick={handleLogout}
              disabled={isLoading}
              title={t('auth.logout.button', '登出')}
            >
              <LogOutIcon size={16} className="text-[#4f7096]" />
            </Button>
          </div>
        )}
      </div>
    </nav>
  );
};