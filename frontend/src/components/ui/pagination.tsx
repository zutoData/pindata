import React from 'react';
import { Button } from './button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';
import { Input } from './input';
import { ChevronLeftIcon, ChevronRightIcon, ChevronsLeftIcon, ChevronsRightIcon } from 'lucide-react';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  className = ''
}) => {
  const [jumpToPage, setJumpToPage] = React.useState('');

  const handleJumpToPage = () => {
    const pageNumber = parseInt(jumpToPage);
    if (pageNumber >= 1 && pageNumber <= totalPages) {
      onPageChange(pageNumber);
      setJumpToPage('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleJumpToPage();
    }
  };

  const getPageNumbers = () => {
    const pages = [];
    const maxVisiblePages = 7;
    
    if (totalPages <= maxVisiblePages) {
      // 显示所有页码
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // 智能显示页码
      let startPage = Math.max(1, currentPage - 2);
      let endPage = Math.min(totalPages, currentPage + 2);
      
      if (currentPage <= 3) {
        endPage = Math.min(5, totalPages);
      } else if (currentPage >= totalPages - 2) {
        startPage = Math.max(1, totalPages - 4);
      }
      
      if (startPage > 1) {
        pages.push(1);
        if (startPage > 2) {
          pages.push('...');
        }
      }
      
      for (let i = startPage; i <= endPage; i++) {
        pages.push(i);
      }
      
      if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
          pages.push('...');
        }
        pages.push(totalPages);
      }
    }
    
    return pages;
  };

  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  return (
    <div className={`flex items-center justify-between ${className}`}>
      <div className="flex items-center space-x-2">
        <span className="text-sm text-[#4f7096]">
          显示 {startItem} 到 {endItem} 条，共 {totalItems} 条
        </span>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-[#4f7096]">每页显示</span>
          <Select value={pageSize.toString()} onValueChange={(value) => onPageSizeChange(parseInt(value))}>
            <SelectTrigger className="w-20 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="20">20</SelectItem>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-sm text-[#4f7096]">条</span>
        </div>
      </div>
      
      <div className="flex items-center space-x-2">
        {/* 快速跳转 */}
        <div className="flex items-center space-x-2">
          <span className="text-sm text-[#4f7096]">跳转至</span>
          <Input
            type="number"
            min="1"
            max={totalPages}
            value={jumpToPage}
            onChange={(e) => setJumpToPage(e.target.value)}
            onKeyPress={handleKeyPress}
            className="w-16 h-8 text-center"
            placeholder="页"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={handleJumpToPage}
            disabled={!jumpToPage || parseInt(jumpToPage) < 1 || parseInt(jumpToPage) > totalPages}
            className="h-8 px-3"
          >
            跳转
          </Button>
        </div>
        
        {/* 分页按钮 */}
        <div className="flex items-center space-x-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(1)}
            disabled={currentPage === 1}
            className="h-8 w-8 p-0"
          >
            <ChevronsLeftIcon className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="h-8 w-8 p-0"
          >
            <ChevronLeftIcon className="h-4 w-4" />
          </Button>
          
          {getPageNumbers().map((page, index) => (
            <React.Fragment key={index}>
              {page === '...' ? (
                <span className="px-2 py-1 text-sm text-[#4f7096]">...</span>
              ) : (
                <Button
                  variant={currentPage === page ? "default" : "outline"}
                  size="sm"
                  onClick={() => onPageChange(page as number)}
                  className="h-8 w-8 p-0"
                >
                  {page}
                </Button>
              )}
            </React.Fragment>
          ))}
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="h-8 w-8 p-0"
          >
            <ChevronRightIcon className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(totalPages)}
            disabled={currentPage === totalPages}
            className="h-8 w-8 p-0"
          >
            <ChevronsRightIcon className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}; 